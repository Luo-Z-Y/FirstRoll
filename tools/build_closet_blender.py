"""Build the FirstRoll walk-in archive as a web-ready Blender GLB.

Run with:
    blender --background --python tools/build_closet_blender.py

The room shell and ambient archive cases live in the GLB. Film-specific cases are
created in the browser so search results remain selectable and up to date.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "app" / "web" / "models" / "firstroll-closet.glb"
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
    if emission:
        emission_input = shader.inputs.get("Emission Color") or shader.inputs.get("Emission")
        if emission_input:
            emission_input.default_value = emission
        strength_input = shader.inputs.get("Emission Strength")
        if strength_input:
            strength_input.default_value = emission_strength
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
    rotation_z: float = 0.0,
) -> None:
    case = box(
        name,
        location,
        dimensions,
        mat,
        bevel=0.012,
        rotation=(0.0, 0.0, rotation_z),
    )
    case["firstroll_ambient_case"] = True


def build_shell(materials: dict[str, bpy.types.Material]) -> None:
    box("Floor slab", (0.0, 0.0, -0.12), (12.4, 15.4, 0.24), materials["structure"], bevel=0.04)
    box("Archive carpet", (0.0, -0.05, 0.015), (11.55, 14.55, 0.03), materials["carpet"], bevel=0.03)
    box("Back wall", (0.0, 7.52, 2.35), (12.4, 0.22, 4.7), materials["wall"], bevel=0.02)
    box("Left wall", (-6.1, 0.0, 2.35), (0.22, 15.2, 4.7), materials["wall"], bevel=0.02)
    box("Right wall", (6.1, 0.0, 2.35), (0.22, 15.2, 4.7), materials["wall"], bevel=0.02)

    # A substantial entrance frame makes walking in and out spatially legible.
    for x in (-5.88, 5.88):
        box("Entrance jamb", (x, -7.32, 2.38), (0.34, 0.46, 4.76), materials["structure"], bevel=0.035)
    box("Entrance lintel", (0.0, -7.32, 4.58), (11.9, 0.46, 0.36), materials["structure"], bevel=0.035)

    # Ceiling ribs and warm recessed light boxes evoke a small physical archive.
    for y in (-5.6, -2.8, 0.0, 2.8, 5.6):
        box("Ceiling rib", (0.0, y, 4.61), (12.0, 0.11, 0.16), materials["structure"], bevel=0.02)
    for y in (-4.2, 0.0, 4.2):
        box("Ceiling light trim", (0.0, y, 4.54), (4.55, 0.9, 0.10), materials["metal"], bevel=0.04)
        box("Ceiling light diffuser", (0.0, y, 4.48), (4.28, 0.67, 0.045), materials["light"], bevel=0.04)


def build_back_shelves(materials: dict[str, bpy.types.Material]) -> None:
    shelf_y = 7.04
    shelf_levels = (0.25, 1.08, 1.91, 2.74, 3.57, 4.40)
    for index, level in enumerate(shelf_levels):
        box(f"Back shelf {index + 1}", (0.0, shelf_y, level), (11.55, 0.72, 0.10), materials["wood"], bevel=0.018)
        box(f"Back shelf brass rail {index + 1}", (0.0, 6.66, level + 0.025), (11.55, 0.045, 0.10), materials["brass"], bevel=0.012)
    for x in (-5.72, -3.82, -1.91, 0.0, 1.91, 3.82, 5.72):
        box("Back shelf upright", (x, 7.28, 2.33), (0.09, 0.18, 4.47), materials["metal"], bevel=0.018)

    # Leave the second row clear: the browser inserts the selected director's live filmography there.
    palette = materials["case_palette"]
    for shelf_index, base_z in enumerate(shelf_levels[:-1]):
        if shelf_index == 1:
            continue
        x = -5.55
        case_index = 0
        while x < 5.48:
            width = random.uniform(0.115, 0.175)
            height = random.uniform(0.48, 0.68)
            depth = random.uniform(0.26, 0.37)
            lean = random.choice((0.0, 0.0, 0.0, random.uniform(-0.035, 0.035)))
            add_case(
                f"Back ambient case {shelf_index}-{case_index}",
                (x + width / 2, 6.77, base_z + 0.07 + height / 2),
                (width, depth, height),
                random.choice(palette),
                rotation_z=lean,
            )
            x += width + random.uniform(0.012, 0.035)
            case_index += 1


def build_side_shelves(side: str, materials: dict[str, bpy.types.Material]) -> None:
    sign = -1.0 if side == "left" else 1.0
    shelf_x = sign * 5.72
    shelf_levels = (0.25, 1.08, 1.91, 2.74, 3.57, 4.40)
    for index, level in enumerate(shelf_levels):
        box(f"{side.title()} shelf {index + 1}", (shelf_x, -0.05, level), (0.72, 14.20, 0.10), materials["wood"], bevel=0.018)
        rail_x = shelf_x - sign * 0.38
        box(f"{side.title()} shelf brass rail {index + 1}", (rail_x, -0.05, level + 0.025), (0.045, 14.2, 0.10), materials["brass"], bevel=0.012)
    for y in (-6.95, -4.65, -2.35, -0.05, 2.25, 4.55, 6.85):
        box(f"{side.title()} shelf upright", (sign * 5.97, y, 2.33), (0.18, 0.09, 4.47), materials["metal"], bevel=0.018)

    palette = materials["case_palette"]
    for shelf_index, base_z in enumerate(shelf_levels[:-1]):
        # Two rows on each side stay open for live relationship collections.
        if shelf_index in (1, 3):
            continue
        y = -6.85
        case_index = 0
        while y < 6.72:
            width = random.uniform(0.115, 0.175)
            height = random.uniform(0.48, 0.68)
            depth = random.uniform(0.26, 0.37)
            add_case(
                f"{side.title()} ambient case {shelf_index}-{case_index}",
                (sign * 5.48, y + width / 2, base_z + 0.07 + height / 2),
                (depth, width, height),
                random.choice(palette),
                rotation_z=random.choice((0.0, 0.0, random.uniform(-0.03, 0.03))),
            )
            y += width + random.uniform(0.012, 0.035)
            case_index += 1


def build_details(materials: dict[str, bpy.types.Material]) -> None:
    # Low plinths and labelled brass strips add the small-scale construction detail missing from CSS.
    for x in (-5.92, 5.92):
        box("Side plinth", (x, -0.05, 0.16), (0.20, 14.4, 0.32), materials["structure"], bevel=0.025)
    box("Back plinth", (0.0, 7.35, 0.16), (11.8, 0.18, 0.32), materials["structure"], bevel=0.025)
    for x in (-4.9, 4.9):
        box("Floor guide", (x, -0.2, 0.04), (0.025, 13.6, 0.018), materials["brass"], bevel=0.008)


def main() -> None:
    clear_scene()
    materials: dict[str, bpy.types.Material | list[bpy.types.Material]] = {
        "structure": material("Blackened steel", (0.035, 0.039, 0.035, 1.0), metallic=0.72, roughness=0.28),
        "metal": material("Shelf steel", (0.12, 0.13, 0.12, 1.0), metallic=0.82, roughness=0.24),
        "wall": material("Charcoal wall", (0.082, 0.079, 0.068, 1.0), roughness=0.82),
        "wood": material("Smoked oak", (0.17, 0.115, 0.065, 1.0), roughness=0.46),
        "brass": material("Aged brass", (0.42, 0.29, 0.11, 1.0), metallic=0.78, roughness=0.34),
        "carpet": material("Archive carpet", (0.105, 0.10, 0.086, 1.0), roughness=0.94),
        "light": material(
            "Warm diffuser",
            (0.95, 0.88, 0.68, 1.0),
            roughness=0.2,
            emission=(1.0, 0.83, 0.55, 1.0),
            emission_strength=4.0,
        ),
    }
    materials["case_palette"] = [
        material("Case oxblood", (0.31, 0.055, 0.038, 1.0), roughness=0.32),
        material("Case bottle green", (0.055, 0.16, 0.10, 1.0), roughness=0.34),
        material("Case burnt orange", (0.48, 0.17, 0.045, 1.0), roughness=0.34),
        material("Case slate", (0.07, 0.11, 0.17, 1.0), roughness=0.30),
        material("Case parchment", (0.48, 0.40, 0.25, 1.0), roughness=0.48),
        material("Case plum", (0.22, 0.08, 0.22, 1.0), roughness=0.36),
    ]

    build_shell(materials)
    build_back_shelves(materials)
    build_side_shelves("left", materials)
    build_side_shelves("right", materials)
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
    print(f"FirstRoll closet exported to {OUTPUT}")


if __name__ == "__main__":
    main()
