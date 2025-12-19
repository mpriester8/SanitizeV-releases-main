"""
Constants and Schema definitions for Sanitize V.
"""

import os

VERSION = "1.1.4"

# Defined Settings Schema for Graphics Editor
SETTINGS_SCHEMA = {
    "Tessellation": {
        "label": "Tessellation",
        "section": "graphics",
        "type": "combobox",
        "options": [("0", "Off"), ("1", "Normal"), ("2", "High"), ("3", "Very High")]
    },
    "ShadowQuality": {
        "label": "Shadow Quality",
        "section": "graphics",
        "type": "combobox",
        "options": [("0", "Off"), ("1", "Normal"), ("2", "High"), ("3", "Very High")]
    },
    "ReflectionQuality": {
        "label": "Reflection Quality",
        "section": "graphics",
        "type": "combobox",
        "options": [("0", "Normal"), ("1", "High"), ("2", "Very High"), ("3", "Ultra")]
    },
    "TextureQuality": {
        "label": "Texture Quality",
        "section": "graphics",
        "type": "combobox",
        "options": [("0", "Normal"), ("1", "High"), ("2", "Very High")]
    },
    "ParticleQuality": {
        "label": "Particle Quality",
        "section": "graphics",
        "type": "combobox",
        "options": [("0", "Normal"), ("1", "High"), ("2", "Very High")]
    },
    "WaterQuality": {
        "label": "Water Quality",
        "section": "graphics",
        "type": "combobox",
        "options": [("0", "Normal"), ("1", "High"), ("2", "Very High")]
    },
    "GrassQuality": {
        "label": "Grass Quality",
        "section": "graphics",
        "type": "combobox",
        "options": [("0", "Normal"), ("1", "High"), ("2", "Very High"), ("3", "Ultra")]
    },
    "ShaderQuality": {
        "label": "Shader Quality",
        "section": "graphics",
        "type": "combobox",
        "options": [("0", "Normal"), ("1", "High"), ("2", "Very High")]
    },
    "Shadow_SoftShadows": {
        "label": "Soft Shadows",
        "section": "graphics",
        "type": "combobox",
        "options": [
            ("0", "Sharp"), ("1", "Soft"), ("2", "Softer"), ("3", "Softest"),
            ("4", "AMD CHS"), ("5", "NVIDIA PCSS")
        ]
    },
    "FXAA_Enabled": {
        "label": "FXAA",
        "section": "graphics",
        "type": "combobox",
        "options": [("true", "True"), ("false", "False")]
    },
    "TXAA_Enabled": {
        "label": "TXAA",
        "section": "graphics",
        "type": "combobox",
        "options": [("true", "True"), ("false", "False")]
    },
    "PostFX": {
        "label": "PostFX",
        "section": "graphics",
        "type": "combobox",
        "options": [("0", "Normal"), ("1", "High"), ("2", "Very High"), ("3", "Ultra")]
    },
    # New Settings
    "SSAO": {
        "label": "SSAO",
        "section": "graphics",
        "type": "combobox",
        "options": [("0", "Off"), ("1", "Normal"), ("2", "High")]
    },
    "UltraShadows_Enabled": {
        "label": "High Resolution Shadows",
        "section": "graphics",
        "type": "combobox",
        "options": [("true", "On"), ("false", "Off")]
    },
    "Shadow_ParticleShadows": {
        "label": "Particle Shadows",
        "section": "graphics",
        "type": "combobox",
        "options": [("true", "On"), ("false", "Off")]
    },
    "Shadow_LongShadows": {
        "label": "Long Shadows",
        "section": "graphics",
        "type": "combobox",
        "options": [("true", "On"), ("false", "Off")]
    },
    "DoF": {
        "label": "Depth of Field (DoF)",
        "section": "graphics",
        "type": "combobox",
        "options": [("true", "On"), ("false", "Off")]
    },
    "HdStreamingInFlight": {
        "label": "High Detail Streaming (Flying)",
        "section": "graphics",
        "type": "combobox",
        "options": [("true", "On"), ("false", "Off")]
    },
    "PauseOnFocusLoss": {
        "label": "Pause Game on Focus Loss",
        "section": "video",
        "type": "combobox",
        "options": [("1", "On"), ("0", "Off")]
    },
    # Sliders
    "LodScale": {
        "label": "Distance Scaling",
        "section": "graphics",
        "type": "slider",
        "ui_range": (0, 10),
        "xml_range": (0.0, 1.0)
    },
    "PedLodBias": {
        "label": "Pedestrian LoD Bias",
        "section": "graphics",
        "type": "slider",
        "ui_range": (0, 10),
        "xml_range": (0.0, 1.0)
    },
    "Shadow_Distance": {
        "label": "Extended Shadow Distance",
        "section": "graphics",
        "type": "slider",
        "ui_range": (0, 10),
        "xml_range": (0.0, 1.0)
    },
    "MaxLodScale": {
        "label": "Extended Distance Scaling",
        "section": "graphics",
        "type": "slider",
        "ui_range": (0, 10),
        "xml_range": (0.0, 1.0)
    },
    "CityDensity": {
        "label": "Population Density",
        "section": "graphics",
        "type": "slider",
        "ui_range": (0, 10),
        "xml_range": (0.0, 1.0)
    },
    "PedVarietyMultiplier": {
        "label": "Population Variety",
        "section": "graphics",
        "type": "slider",
        "ui_range": (0, 10),
        "xml_range": (0.0, 1.0)
    },
    "VehicleVarietyMultiplier": {
        "label": "Vehicle Variety",
        "section": "graphics",
        "type": "slider",
        "ui_range": (0, 10),
        "xml_range": (0.0, 1.0)
    },
    "MotionBlurStrength": {
        "label": "Motion Blur Strength",
        "section": "graphics",
        "type": "slider",
        "ui_range": (0, 10),
        "xml_range": (0.0, 1.0)
    }
}

# Constants for default paths
LOCAL_APP_DATA = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
APP_DATA = os.getenv('APPDATA', os.path.expanduser('~'))

DEFAULT_XML_SOURCE_DIR = os.path.join(APP_DATA, 'CitizenFX')
FOLDER1_NAME = "mods"
FOLDER2_NAME = "plugins"
XML_FILENAME = "gta5_settings.xml"

# Determine best guess for FiveM Source Directory
candidate_paths = [
    os.path.join(LOCAL_APP_DATA, 'FiveM', 'FiveM.app'),
    os.path.join(LOCAL_APP_DATA, 'FiveM', 'FiveM Application Data')
]
DEFAULT_SOURCE_DIR = os.path.join(LOCAL_APP_DATA, 'FiveM')
for path in candidate_paths:
    if os.path.exists(path):
        DEFAULT_SOURCE_DIR = path
        break
