"""Ejecutar UNA VEZ en Unreal Editor: Tools -> Execute Python Script.
Crea materiales reales .uasset con Base Color, Roughness y Metallic, sin contenido externo.
"""
import unreal

DIR = '/Game/StudyRoom/Materials'
COLORS = {
    'Wall': ((0.65, 0.70, 0.68), .92, .0),
    'Accent': ((0.12, 0.29, 0.28), .85, .0),
    'Floor': ((0.30, 0.20, 0.12), .61, .0),
    'Wood': ((0.48, 0.29, 0.14), .63, .0),
    'Dark': ((0.035, 0.055, 0.064), .35, .18),
    'Fabric': ((0.21, 0.26, 0.27), .95, .0),
    'LightFabric': ((0.59, 0.52, 0.42), .98, .0),
    'White': ((0.84, 0.81, 0.72), .82, .0),
    'Green': ((0.08, 0.26, 0.12), .85, .0),
    'Ceramic': ((0.55, 0.31, 0.19), .28, .05),
    'Screen': ((0.018, 0.072, 0.12), .22, .10),
    'Sky': ((0.20, 0.40, 0.57), .60, .0),
    'Art': ((0.68, 0.29, 0.14), .87, .0),
}
assets = unreal.AssetToolsHelpers.get_asset_tools()
unreal.EditorAssetLibrary.make_directory(DIR)
for key, (rgb, roughness, metallic) in COLORS.items():
    full = f'{DIR}/M_{key}'
    if unreal.EditorAssetLibrary.does_asset_exist(full):
        mat = unreal.EditorAssetLibrary.load_asset(full)
        print(f'Sin modificar (ya existe): {full}')
        continue
    mat = assets.create_asset('M_'+key, DIR, unreal.Material, unreal.MaterialFactoryNew())
    color = unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -380, -150)
    color.set_editor_property('parameter_name', 'Tint')
    color.set_editor_property('default_value', unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
    unreal.MaterialEditingLibrary.connect_material_property(color, '', unreal.MaterialProperty.MP_BASE_COLOR)
    r = unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionConstant, -360, 80)
    r.set_editor_property('r', float(roughness))
    unreal.MaterialEditingLibrary.connect_material_property(r, '', unreal.MaterialProperty.MP_ROUGHNESS)
    m = unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionConstant, -360, 250)
    m.set_editor_property('r', float(metallic))
    unreal.MaterialEditingLibrary.connect_material_property(m, '', unreal.MaterialProperty.MP_METALLIC)
    unreal.MaterialEditingLibrary.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    print('Creado:', full)
print('13 materiales listos. Selecciona StudyRoomBuilder y modifica temporalmente Brightness para regenerar la sala.')
