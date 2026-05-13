"""
Parse entity data from binary GTA V .ymap files.

Binary .ymap files use the RSC7 container format:
  - 16-byte header: magic ('RSC7'), version (2), systemFlags, graphicsFlags
  - Raw DEFLATE-compressed payload (system segment + graphics segment)

The system segment is a "Meta" binary structure (virtual base 0x50000000) that
describes blocks of typed structured data.  We walk the Meta's DataBlocks to
find the CEntityDef array and its StructureInfo (field offsets), then read each
entity's archetypeName hash and world position.

This is intentionally read-only.  Writing back binary .ymap is not implemented.

Reference: CodeWalker (dexyfex/CodeWalker) and
           carmineos/gta-toolkit — both MIT-licensed open-source projects.
"""
from __future__ import annotations

import zlib
import struct
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Virtual base address for the system segment in RSC7 resources.
_SYS_BASE: int = 0x50000000


# ---------------------------------------------------------------------------
# Jenkins one-at-a-time hash (GTA V variant — same as "joaat")
# ---------------------------------------------------------------------------

def _jenkins_hash(s: str) -> int:
    """Return the GTA V Jenkins one-at-a-time hash of *s* (case-insensitive)."""
    h = 0
    for c in s.lower():
        h = (h + ord(c)) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h


# Pre-computed hashes for the names we care about.
_H_CENTITYDEF: int = _jenkins_hash("CEntityDef")
_H_ARCHETYPE:  int = _jenkins_hash("archetypeName")
_H_POSITION:   int = _jenkins_hash("position")


# ---------------------------------------------------------------------------
# Public data type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BinaryEntity:
    """One CEntityDef entry extracted from a binary .ymap file."""
    archetype_hash: int   # Jenkins hash of the archetype model name
    x: float
    y: float
    z: float

    def key(self) -> tuple[int, str, str, str]:
        """
        Deduplication key.  Positions are rounded to 2 decimal places to
        absorb floating-point jitter, matching the .ymap.xml logic.
        """
        return (self.archetype_hash,
                f"{self.x:.2f}", f"{self.y:.2f}", f"{self.z:.2f}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _vptr_to_offset(ptr: int) -> int:
    """Strip the high segment nibble from a virtual pointer → raw offset."""
    return ptr & 0x0FFF_FFFF


class _Buf:
    """Thin wrapper around a bytes buffer for safe fixed-size reads."""

    __slots__ = ("_data",)

    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self, offset: int, fmt: str) -> tuple | None:
        size = struct.calcsize(fmt)
        if offset < 0 or offset + size > len(self._data):
            return None
        return struct.unpack_from(fmt, self._data, offset)

    def slice(self, offset: int, length: int) -> bytes | None:
        if offset < 0 or offset + length > len(self._data):
            return None
        return self._data[offset: offset + length]

    def __len__(self) -> int:
        return len(self._data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_binary_ymap_entities(path: Path) -> list[BinaryEntity] | None:
    """
    Parse *CEntityDef* entity data from a binary ``.ymap`` file.

    Returns:
        - ``list[BinaryEntity]`` (may be empty) on success.
        - ``None`` if *path* is not a valid binary .ymap or cannot be parsed
          (e.g. corrupted, wrong format, unsupported variant).

    This function is pure-read; it never modifies *path*.
    """
    try:
        raw_file = path.read_bytes()
    except OSError as exc:
        logger.debug("ymap_binary: cannot read %s: %s", path, exc)
        return None

    return _parse_bytes(raw_file)


def _parse_bytes(data: bytes) -> list[BinaryEntity] | None:
    """Parse entity data from the raw bytes of a binary .ymap file."""

    # ── RSC7 header (16 bytes) ───────────────────────────────────────────────
    if len(data) < 16:
        return None

    hdr = struct.unpack_from("<IIII", data, 0)
    magic, version, sys_flags, gfx_flags = hdr
    if magic != 0x37435352:          # 'RSC7'
        return None

    # ── Decompress the payload (raw DEFLATE — no zlib header) ───────────────
    try:
        raw = zlib.decompress(data[16:], wbits=-15)
    except zlib.error as exc:
        logger.debug("ymap_binary: decompress failed: %s", exc)
        return None

    buf = _Buf(raw)

    # ── Locate MetaData header ───────────────────────────────────────────────
    # Layout in decompressed system segment (virtual base 0x50000000):
    #   [0x00-0x0F]  PgBase64 header  (vtable ptr 8 + pagemap ptr 8)
    #   [0x10]       int32  signature  = 0x50524430  ('PRD0')
    #   [0x14]       int16  = 0x0079
    #   [0x16]       byte   HasUselessData
    #   [0x17]       byte   padding
    #   [0x18]       int32  = 0
    #   [0x1C]       int32  RootBlockIndex
    #   [0x20]       int64  StructureInfosPointer
    #   [0x28]       int64  EnumInfosPointer
    #   [0x30]       int64  DataBlocksPointer
    #   [0x38]       int64  NamePointer
    #   [0x40]       int64  UselessPointer
    #   [0x48]       int16  StructureInfosCount
    #   [0x4A]       int16  EnumInfosCount
    #   [0x4C]       int16  DataBlocksCount
    META_SIG_OFF = 0x10
    sig_v = buf.read(META_SIG_OFF, "<I")
    if sig_v is None or sig_v[0] != 0x50524430:
        logger.debug("ymap_binary: missing PRD0 signature")
        return None

    ptrs = buf.read(0x20, "<QQQ")   # struct_infos_ptr, enum_infos_ptr, data_blocks_ptr
    if ptrs is None:
        return None
    struct_infos_ptr, _enum_infos_ptr, data_blocks_ptr = ptrs

    counts = buf.read(0x48, "<HHH")  # struct_infos_count, enum_infos_count, data_blocks_count
    if counts is None:
        return None
    struct_infos_count, _enum_infos_count, data_blocks_count = counts

    # ── Scan DataBlocks for the CEntityDef block ─────────────────────────────
    # DataBlock layout (16 bytes = 0x10):
    #   int32 StructureNameHash
    #   int32 DataLength
    #   int64 DataPointer
    db_base = _vptr_to_offset(data_blocks_ptr)
    entity_block: bytes | None = None

    for i in range(data_blocks_count):
        row = buf.read(db_base + i * 0x10, "<IIQ")
        if row is None:
            break
        name_hash, data_length, data_ptr = row
        if name_hash == _H_CENTITYDEF:
            d_off = _vptr_to_offset(data_ptr)
            entity_block = buf.slice(d_off, data_length)
            break

    if not entity_block:
        # No entity block → valid ymap with no CEntityDef entries (e.g. grass-only)
        return []

    # ── Read StructureInfos to find CEntityDef field offsets ─────────────────
    # StructureInfo layout (32 bytes = 0x20):
    #   int32  StructureNameHash
    #   int32  StructureKey
    #   int32  Unknown_8h
    #   int32  Unknown_Ch
    #   int64  EntriesPointer
    #   int32  StructureLength
    #   int16  Unknown_1Ch
    #   int16  EntriesCount
    si_base = _vptr_to_offset(struct_infos_ptr)
    archetype_field_off: int | None = None
    position_field_off: int | None = None
    entity_struct_len: int | None = None

    for i in range(struct_infos_count):
        si = buf.read(si_base + i * 0x20, "<IIIIQiHH")
        if si is None:
            break
        si_hash, _, _, _, entries_ptr, si_struct_len, _, entries_count = si
        if si_hash != _H_CENTITYDEF:
            continue
        entity_struct_len = si_struct_len

        # ── StructureEntryInfo layout (16 bytes = 0x10) ──────────────────────
        #   int32   EntryNameHash
        #   int32   DataOffset
        #   byte    DataType
        #   byte    Unknown_9h
        #   int16   ReferenceTypeIndex
        #   int32   ReferenceKey
        e_base = _vptr_to_offset(entries_ptr)
        for j in range(entries_count):
            e = buf.read(e_base + j * 0x10, "<IIBBhI")
            if e is None:
                break
            e_hash, e_offset, _e_type, _, _, _ = e
            if e_hash == _H_ARCHETYPE:
                archetype_field_off = e_offset
            elif e_hash == _H_POSITION:
                position_field_off = e_offset
            if archetype_field_off is not None and position_field_off is not None:
                break
        break

    if archetype_field_off is None or position_field_off is None or not entity_struct_len:
        logger.debug(
            "ymap_binary: could not find field offsets in CEntityDef "
            "(archetype_off=%s, position_off=%s, struct_len=%s)",
            archetype_field_off, position_field_off, entity_struct_len,
        )
        return []

    # ── Parse entity structs ─────────────────────────────────────────────────
    n_entities = len(entity_block) // entity_struct_len
    eb = _Buf(entity_block)
    entities: list[BinaryEntity] = []

    for i in range(n_entities):
        base = i * entity_struct_len
        arch = eb.read(base + archetype_field_off, "<I")
        pos  = eb.read(base + position_field_off,  "<fff")
        if arch is None or pos is None:
            logger.debug("ymap_binary: short read at entity %d", i)
            break
        entities.append(BinaryEntity(arch[0], pos[0], pos[1], pos[2]))

    return entities
