"""Build the FirstRoll single-wall film shelf as a web-ready Blender GLB.

Run with:
    blender --background --python tools/build_closet_blender.py

The gallery shell and ambient archive cases live in the GLB. Film-specific cases are
created in the browser so search results remain selectable and up to date.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "app" / "web" / "models" / "firstroll-closet.glb"
ROOM_HALF_WIDTH = 1.8
ROOM_HALF_DEPTH = 4.6
ROOM_WIDTH = ROOM_HALF_WIDTH * 2
ROOM_DEPTH = ROOM_HALF_DEPTH * 2
BACK_WALL_Y = 4.52
SIDE_WALL_X = 1.7
BACK_SHELF_Y = 4.04
BACK_CASE_Y = 3.77
random.seed(817)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in bpy.data.materials:
        bpy.data.materials.remove(block)


def material(
    name: str,
    colour: tuple[float, float, float, float],
    *,
    metallic: float = 0.0,
    roughness: float = 0.55,
    emission: tuple[float, float, float, float] | None = None,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = colour
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = colour
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Alpha"].default_value = colour[3]
    if colour[3] < 1.0 and hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "DITHERED"
    if emission:
        emission_input = shader.inputs.get("Emission Color") or shader.inputs.get("Emission")
        if emission_input:
            emission_input.default_value = emission
        strength_input = shader.inputs.get("Emission Strength")
        if strength_input:
            strength_input.default_value = emission_strength
    return mat


def textured_material(
    name: str,
    base: tuple[float, float, float],
    texture_kind: str,
    *,
    roughness: float,
    size: int = 160,
) -> bpy.types.Material:
    """Create and pack a small deterministic colour texture into the exported GLB."""
    mat = material(name, (*base, 1.0), roughness=roughness)
    image = bpy.data.images.new(f"{name} texture", width=size, height=size, alpha=False)
    rng = random.Random(f"firstroll-{name}")
    pixels: list[float] = []
    for y in range(size):
        for x in range(size):
            if texture_kind == "wood":
                grain = (
                    math.sin(x * 0.22 + math.sin(y * 0.075) * 2.4) * 0.065
                    + math.sin(x * 0.055 + y * 0.014) * 0.035
                    + rng.uniform(-0.025, 0.025)
                )
                value = 1.0 + grain
            elif texture_kind == "carpet":
                fleck = rng.uniform(-0.12, 0.12)
                value = 1.0 + fleck
            else:
                mottling = (
                    math.sin(x * 0.048) * math.sin(y * 0.063) * 0.035
                    + rng.uniform(-0.025, 0.025)
                )
                value = 1.0 + mottling
            pixels.extend((*[max(0.0, min(1.0, channel * value)) for channel in base], 1.0))
    image.pixels = pixels
    image.pack()
    texture = mat.node_tree.nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.interpolation = "Linear"
    shader = mat.node_tree.nodes.get("Principled BSDF")
    mat.node_tree.links.new(texture.outputs["Color"], shader.inputs["Base Color"])
    return mat


def box(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    mat: bpy.types.Material,
    *,
    bevel: float = 0.025,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        modifier = obj.modifiers.new("Softened edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
    return obj


def add_case(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    mat: bpy.types.Material,
    *,
    shell_material: bpy.types.Material,
    sideways: bool = False,
    rotation_z: float = 0.0,
) -> None:
    insert_dimensions = (
        dimensions[0] * (0.35 if sideways else 0.82),
        dimensions[1] * (0.86 if sideways else 0.35),
        dimensions[2] * 0.91,
    )
    insert = box(
        f"{name} paper insert",
        location,
        insert_dimensions,
        mat,
        bevel=0.007,
        rotation=(0.0, 0.0, rotation_z),
    )
    insert["firstroll_ambient_case"] = True
    shell = box(
        f"{name} clear shell",
        location,
        dimensions,
        shell_material,
        bevel=0.014,
        rotation=(0.0, 0.0, rotation_z),
    )
    shell["firstroll_ambient_case"] = True


def build_shell(materials: dict[str, bpy.types.Material]) -> None:
    box("Floor slab", (0.0, 0.0, -0.12), (ROOM_WIDTH, ROOM_DEPTH, 0.24), materials["structure"], bevel=0.04)
    box("Archive carpet", (0.0, -0.05, 0.015), (3.18, 8.72, 0.03), materials["carpet"], bevel=0.03)
    box("Back wall", (0.0, BACK_WALL_Y, 2.35), (ROOM_WIDTH, 0.22, 4.7), materials["wall"], bevel=0.02)
    box("Left wall", (-SIDE_WALL_X, 0.0, 2.35), (0.22, ROOM_DEPTH, 4.7), materials["wall"], bevel=0.02)
    box("Right wall", (SIDE_WALL_X, 0.0, 2.35), (0.22, ROOM_DEPTH, 4.7), materials["wall"], bevel=0.02)

    # A substantial entrance frame makes walking in and out spatially legible.
    for x in (-1.58, 1.58):
        box("Entrance jamb", (x, -4.32, 2.38), (0.34, 0.46, 4.76), materials["structure"], bevel=0.035)
    box("Entrance lintel", (0.0, -4.32, 4.58), (3.5, 0.46, 0.36), materials["structure"], bevel=0.035)

    # Ceiling ribs and warm recessed light boxes evoke a small physical archive.
    for y in (-3.45, -1.72, 0.0, 1.72, 3.45):
        box("Ceiling rib", (0.0, y, 4.61), (3.42, 0.11, 0.16), materials["structure"], bevel=0.02)
    for y in (-2.8, 0.0, 2.8):
        box("Ceiling light trim", (0.0, y, 4.54), (2.42, 0.76, 0.10), materials["metal"], bevel=0.04)
        box("Ceiling light diffuser", (0.0, y, 4.48), (2.22, 0.56, 0.045), materials["light"], bevel=0.04)


def build_back_shelves(materials: dict[str, bpy.types.Material]) -> None:
    shelf_levels = (0.25, 1.08, 1.91, 2.74, 3.57, 4.40)
    for index, level in enumerate(shelf_levels):
        box(f"Back shelf {index + 1}", (0.0, BACK_SHELF_Y, level), (3.15, 0.72, 0.10), materials["wood"], bevel=0.018)
        box(f"Back shelf brass rail {index + 1}", (0.0, 3.66, level + 0.025), (3.15, 0.045, 0.10), materials["brass"], bevel=0.012)
    for x in (-1.56, 0.0, 1.56):
        box("Back shelf upright", (x, 4.28, 2.33), (0.09, 0.18, 4.47), materials["metal"], bevel=0.018)

    # Leave three distinct rows clear for live director, context and related-film cases.
    palette = materials["case_palette"]
    for shelf_index, base_z in enumerate(shelf_levels[:-1]):
        if shelf_index in (1, 2, 3):
            continue
        x = -1.46
        case_index = 0
        while x < 1.44:
            width = random.uniform(0.16, 0.22)
            height = random.uniform(0.48, 0.68)
            depth = random.uniform(0.11, 0.15)
            add_case(
                f"Back ambient case {shelf_index}-{case_index}",
                (x + width / 2, BACK_CASE_Y, base_z + 0.07 + height / 2),
                (width, depth, height),
                random.choice(palette),
                shell_material=materials["case_shell"],
                rotation_z=0.0,
            )
            x += width + random.uniform(0.028, 0.052)
            case_index += 1


def build_details(materials: dict[str, bpy.types.Material]) -> None:
    # Low plinths and labelled brass strips add the small-scale construction detail missing from CSS.
    for x in (-1.68, 1.68):
        box("Side plinth", (x, -0.05, 0.16), (0.20, 8.7, 0.32), materials["structure"], bevel=0.025)
    box("Back plinth", (0.0, 4.35, 0.16), (3.34, 0.18, 0.32), materials["structure"], bevel=0.025)
    for x in (-1.22, 1.22):
        box("Floor guide", (x, -0.2, 0.04), (0.025, 7.9, 0.018), materials["brass"], bevel=0.008)


def main() -> None:
    clear_scene()
    materials: dict[str, bpy.types.Material | list[bpy.types.Material]] = {
        "structure": material("Blackened steel", (0.035, 0.039, 0.035, 1.0), metallic=0.72, roughness=0.28),
        "metal": material("Shelf steel", (0.12, 0.13, 0.12, 1.0), metallic=0.82, roughness=0.24),
        "wall": textured_material("Charcoal wall", (0.065, 0.058, 0.047), "plaster", roughness=0.86),
        "wood": textured_material("Smoked oak", (0.16, 0.092, 0.045), "wood", roughness=0.52),
        "brass": material("Aged brass", (0.42, 0.29, 0.11, 1.0), metallic=0.78, roughness=0.34),
        "carpet": textured_material("Archive carpet", (0.095, 0.078, 0.061), "carpet", roughness=0.96),
        "case_shell": material("Clear jewel case", (0.82, 0.84, 0.80, 0.16), roughness=0.16),
        "light": material(
            "Warm diffuser",
            (0.95, 0.88, 0.68, 1.0),
            roughness=0.2,
            emission=(1.0, 0.83, 0.55, 1.0),
            emission_strength=4.0,
        ),
    }
    materials["case_palette"] = [
        material("Insert oxblood", (0.255, 0.066, 0.045, 1.0), roughness=0.58),
        material("Insert bottle green", (0.062, 0.132, 0.087, 1.0), roughness=0.58),
        material("Insert tobacco", (0.34, 0.145, 0.056, 1.0), roughness=0.60),
        material("Insert slate", (0.085, 0.108, 0.132, 1.0), roughness=0.56),
        material("Insert parchment", (0.46, 0.395, 0.277, 1.0), roughness=0.68),
        material("Insert plum", (0.185, 0.085, 0.155, 1.0), roughness=0.60),
        material("Insert ivory", (0.62, 0.58, 0.49, 1.0), roughness=0.72),
        material("Insert charcoal", (0.11, 0.105, 0.092, 1.0), roughness=0.66),
    ]

    build_shell(materials)
    build_back_shelves(materials)
    # The live archive is intentionally a single shelf wall. Side walls remain
    # quiet architectural surfaces, preventing perpendicular rows from crossing
    # one another in perspective.
    build_details(materials)

    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    bpy.context.scene.world.color = (0.006, 0.007, 0.006)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(OUTPUT),
        export_format="GLB",
        export_apply=True,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
        export_materials="EXPORT",
        export_yup=True,
    )
    print(f"FirstRoll shelf exported to {OUTPUT}")


if __name__ == "__main__":
    main()
