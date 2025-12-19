"""
Graphics preset configurations for Sanitize V.
"""

# Graphics quality presets
GRAPHICS_PRESETS = {
    "Low": {
        "Tessellation": "0",
        "ShadowQuality": "0",
        "ReflectionQuality": "0",
        "TextureQuality": "0",
        "ParticleQuality": "0",
        "WaterQuality": "0",
        "GrassQuality": "0",
        "ShaderQuality": "0",
        "PostFX": "0",
        "AnisotropicFiltering": "0",
        "MSAA": "0",
        "FXAA": "0",
        "ReflectionMSAA": "0",
        "TXAA": "0",
        "Distance_ParticleQuality": "10",
        "Distance_ShadowDistance": "10",
        "Distance_HeadlightShadows": "10",
        "Distance_ScalingFar": "1.000000",
        "Distance_ScalingNear": "1.000000",
        "Distance_LodScale": "1.000000",
        "Density_LightsScale": "0.500000",
        "Density_PedsScale": "0.500000",
        "Density_VehiclesScale": "0.500000",
        "Density_ParkedCars": "0.500000"
    },
    "Medium": {
        "Tessellation": "1",
        "ShadowQuality": "1",
        "ReflectionQuality": "1",
        "TextureQuality": "1",
        "ParticleQuality": "1",
        "WaterQuality": "1",
        "GrassQuality": "1",
        "ShaderQuality": "1",
        "PostFX": "1",
        "AnisotropicFiltering": "4",
        "MSAA": "2",
        "FXAA": "1",
        "ReflectionMSAA": "2",
        "TXAA": "0",
        "Distance_ParticleQuality": "50",
        "Distance_ShadowDistance": "50",
        "Distance_HeadlightShadows": "50",
        "Distance_ScalingFar": "1.000000",
        "Distance_ScalingNear": "1.000000",
        "Distance_LodScale": "1.000000",
        "Density_LightsScale": "1.000000",
        "Density_PedsScale": "1.000000",
        "Density_VehiclesScale": "1.000000",
        "Density_ParkedCars": "1.000000"
    },
    "High": {
        "Tessellation": "2",
        "ShadowQuality": "2",
        "ReflectionQuality": "2",
        "TextureQuality": "2",
        "ParticleQuality": "2",
        "WaterQuality": "2",
        "GrassQuality": "2",
        "ShaderQuality": "2",
        "PostFX": "2",
        "AnisotropicFiltering": "8",
        "MSAA": "4",
        "FXAA": "1",
        "ReflectionMSAA": "4",
        "TXAA": "0",
        "Distance_ParticleQuality": "75",
        "Distance_ShadowDistance": "75",
        "Distance_HeadlightShadows": "75",
        "Distance_ScalingFar": "1.000000",
        "Distance_ScalingNear": "1.000000",
        "Distance_LodScale": "1.000000",
        "Density_LightsScale": "1.000000",
        "Density_PedsScale": "1.000000",
        "Density_VehiclesScale": "1.000000",
        "Density_ParkedCars": "1.000000"
    },
    "Ultra": {
        "Tessellation": "3",
        "ShadowQuality": "3",
        "ReflectionQuality": "3",
        "TextureQuality": "2",
        "ParticleQuality": "2",
        "WaterQuality": "2",
        "GrassQuality": "2",
        "ShaderQuality": "2",
        "PostFX": "2",
        "AnisotropicFiltering": "16",
        "MSAA": "8",
        "FXAA": "1",
        "ReflectionMSAA": "8",
        "TXAA": "1",
        "Distance_ParticleQuality": "100",
        "Distance_ShadowDistance": "100",
        "Distance_HeadlightShadows": "100",
        "Distance_ScalingFar": "1.000000",
        "Distance_ScalingNear": "1.000000",
        "Distance_LodScale": "1.000000",
        "Density_LightsScale": "1.000000",
        "Density_PedsScale": "1.000000",
        "Density_VehiclesScale": "1.000000",
        "Density_ParkedCars": "1.000000"
    }
}


def get_preset_names():
    """Get list of available preset names."""
    return list(GRAPHICS_PRESETS.keys())


def get_preset_settings(preset_name: str):
    """Get settings for a specific preset."""
    return GRAPHICS_PRESETS.get(preset_name, {})


def apply_preset_to_xml(xml_path: str, preset_name: str) -> bool:
    """
    Apply a graphics preset to an XML file.
    
    Args:
        xml_path: Path to gta5_settings.xml
        preset_name: Name of preset (Low, Medium, High, Ultra)
    
    Returns:
        True if successful
    """
    try:
        import xml.etree.ElementTree as ET
        
        preset = get_preset_settings(preset_name)
        if not preset:
            return False
        
        # Parse XML
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Apply preset values
        for setting_name, value in preset.items():
            # Handle different naming conventions
            if setting_name.startswith("Distance_"):
                elem_name = setting_name.replace("Distance_", "")
                elem = root.find(f".//distance[@{elem_name}]")
                if elem is not None:
                    elem.set(elem_name, value)
            elif setting_name.startswith("Density_"):
                elem_name = setting_name.replace("Density_", "")
                elem = root.find(f".//density[@{elem_name}]")
                if elem is not None:
                    elem.set(elem_name, value)
            else:
                # Regular setting
                elem = root.find(f".//*[@{setting_name}]")
                if elem is not None:
                    elem.set(setting_name, value)
        
        # Save XML
        tree.write(xml_path, encoding='utf-8', xml_declaration=True)
        return True
    except Exception as e:
        print(f"Error applying preset: {e}")
        return False
