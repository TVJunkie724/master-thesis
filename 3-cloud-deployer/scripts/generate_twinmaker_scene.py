#!/usr/bin/env python3
"""
One-time script to generate a 3D glTF scene for AWS IoT TwinMaker.

This script creates a simple 3D scene representing the digital twin hierarchy:
- room-1: Contains machine-1 (with temperature-sensor-1) and temperature-sensor-2
- room-2: Contains pressure-sensor-1

Requirements:
    pip install trimesh numpy

Output:
    - scene_assets/digital_twin_scene.glb (binary glTF)
    - scene_assets/scene.json (TwinMaker scene definition)

Usage:
    python scripts/generate_twinmaker_scene.py
"""

import os
import json
import numpy as np

try:
    import trimesh
except ImportError:
    print("ERROR: trimesh is required. Install with: pip install trimesh numpy")
    print("Or run: docker exec cloud-deployer pip install trimesh numpy")
    exit(1)


# =============================================================================
# Configuration
# =============================================================================

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "upload", "template", "scene_assets")

# Colors (RGBA)
COLORS = {
    "room_floor": [0.9, 0.95, 1.0, 1.0],        # Light blue-gray
    "room_walls": [0.95, 0.95, 0.95, 0.3],      # Translucent white
    "machine": [0.4, 0.45, 0.5, 1.0],           # Industrial gray
    "temp_sensor": [1.0, 0.4, 0.2, 1.0],        # Orange-red (heat)
    "pressure_sensor": [0.2, 0.6, 1.0, 1.0],    # Blue (pressure)
    "label": [0.2, 0.2, 0.2, 1.0],              # Dark gray
}

# Dimensions
ROOM_SIZE = (8.0, 0.2, 6.0)      # Width, Height (floor), Depth
WALL_HEIGHT = 3.0
WALL_THICKNESS = 0.1
MACHINE_SIZE = (2.0, 1.5, 1.5)   # Industrial machine
SENSOR_RADIUS = 0.25             # Sensor sphere radius
ROOM_SPACING = 2.0               # Space between rooms


# =============================================================================
# Geometry Creation Functions
# =============================================================================

def create_room(position, name, color_floor, color_walls):
    """Create a room with floor and transparent walls."""
    meshes = []
    
    x, y, z = position
    w, h, d = ROOM_SIZE
    
    # Floor
    floor = trimesh.creation.box(extents=[w, h, d])
    floor.apply_translation([x + w/2, y, z + d/2])
    floor.visual.face_colors = [int(c * 255) for c in color_floor]
    meshes.append(floor)
    
    # Walls (4 sides)
    # Back wall
    back_wall = trimesh.creation.box(extents=[w, WALL_HEIGHT, WALL_THICKNESS])
    back_wall.apply_translation([x + w/2, y + WALL_HEIGHT/2, z])
    back_wall.visual.face_colors = [int(c * 255) for c in color_walls]
    meshes.append(back_wall)
    
    # Front wall (partial - opening)
    front_wall = trimesh.creation.box(extents=[w, WALL_HEIGHT, WALL_THICKNESS])
    front_wall.apply_translation([x + w/2, y + WALL_HEIGHT/2, z + d])
    front_wall.visual.face_colors = [int(c * 255) for c in color_walls]
    meshes.append(front_wall)
    
    # Left wall
    left_wall = trimesh.creation.box(extents=[WALL_THICKNESS, WALL_HEIGHT, d])
    left_wall.apply_translation([x, y + WALL_HEIGHT/2, z + d/2])
    left_wall.visual.face_colors = [int(c * 255) for c in color_walls]
    meshes.append(left_wall)
    
    # Right wall
    right_wall = trimesh.creation.box(extents=[WALL_THICKNESS, WALL_HEIGHT, d])
    right_wall.apply_translation([x + w, y + WALL_HEIGHT/2, z + d/2])
    right_wall.visual.face_colors = [int(c * 255) for c in color_walls]
    meshes.append(right_wall)
    
    return meshes


def create_machine(position, color):
    """Create an industrial machine (box with details)."""
    meshes = []
    x, y, z = position
    w, h, d = MACHINE_SIZE
    
    # Main body
    body = trimesh.creation.box(extents=[w, h, d])
    body.apply_translation([x, y + h/2, z])
    body.visual.face_colors = [int(c * 255) for c in color]
    meshes.append(body)
    
    # Control panel (small box on front)
    panel = trimesh.creation.box(extents=[w * 0.6, h * 0.4, 0.1])
    panel.apply_translation([x, y + h * 0.7, z + d/2 + 0.05])
    panel.visual.face_colors = [50, 50, 50, 255]  # Dark gray
    meshes.append(panel)
    
    # Vent on top
    vent = trimesh.creation.box(extents=[w * 0.3, 0.1, d * 0.8])
    vent.apply_translation([x, y + h + 0.05, z])
    vent.visual.face_colors = [30, 30, 30, 255]  # Black
    meshes.append(vent)
    
    return meshes


def create_sensor(position, color, sensor_type="temperature"):
    """Create a sensor (sphere with indicator)."""
    meshes = []
    x, y, z = position
    
    # Main sensor body (sphere)
    sensor = trimesh.creation.icosphere(radius=SENSOR_RADIUS, subdivisions=2)
    sensor.apply_translation([x, y + SENSOR_RADIUS, z])
    sensor.visual.face_colors = [int(c * 255) for c in color]
    meshes.append(sensor)
    
    # Mounting bracket (cylinder)
    bracket = trimesh.creation.cylinder(radius=0.05, height=0.3)
    bracket.apply_translation([x, y + 0.15, z])
    bracket.visual.face_colors = [100, 100, 100, 255]  # Gray
    meshes.append(bracket)
    
    # Indicator ring
    ring = trimesh.creation.annulus(r_min=SENSOR_RADIUS * 0.6, r_max=SENSOR_RADIUS * 0.8, height=0.02)
    ring.apply_translation([x, y + SENSOR_RADIUS * 2, z])
    ring.visual.face_colors = [255, 255, 255, 255]  # White
    meshes.append(ring)
    
    return meshes


def create_label(text, position, color):
    """Create a simple label indicator (flat box placeholder)."""
    # Note: trimesh doesn't support text, so we create a small indicator
    x, y, z = position
    label = trimesh.creation.box(extents=[len(text) * 0.15, 0.05, 0.3])
    label.apply_translation([x, y, z])
    label.visual.face_colors = [int(c * 255) for c in color]
    return label


# =============================================================================
# Scene Assembly
# =============================================================================

def build_scene():
    """Build the complete digital twin scene."""
    all_meshes = []
    
    # -------------------------------------------------------------------------
    # ROOM 1 (left side)
    # -------------------------------------------------------------------------
    room1_pos = (0, 0, 0)
    room1_meshes = create_room(room1_pos, "room-1", COLORS["room_floor"], COLORS["room_walls"])
    all_meshes.extend(room1_meshes)
    
    # Machine-1 (inside room-1)
    machine1_pos = (3.0, 0.1, 2.5)  # Centered in room
    machine1_meshes = create_machine(machine1_pos, COLORS["machine"])
    all_meshes.extend(machine1_meshes)
    
    # Temperature-sensor-1 (on machine-1)
    temp1_pos = (3.0, MACHINE_SIZE[1] + 0.1, 2.5)  # On top of machine
    temp1_meshes = create_sensor(temp1_pos, COLORS["temp_sensor"], "temperature")
    all_meshes.extend(temp1_meshes)
    
    # Temperature-sensor-2 (standalone in room-1)
    temp2_pos = (6.0, 0.1, 4.0)  # Near wall
    temp2_meshes = create_sensor(temp2_pos, COLORS["temp_sensor"], "temperature")
    all_meshes.extend(temp2_meshes)
    
    # -------------------------------------------------------------------------
    # ROOM 2 (right side)
    # -------------------------------------------------------------------------
    room2_pos = (ROOM_SIZE[0] + ROOM_SPACING, 0, 0)
    room2_meshes = create_room(room2_pos, "room-2", COLORS["room_floor"], COLORS["room_walls"])
    all_meshes.extend(room2_meshes)
    
    # Pressure-sensor-1 (in room-2)
    pressure1_pos = (room2_pos[0] + 4.0, 0.1, 3.0)  # Center of room
    pressure1_meshes = create_sensor(pressure1_pos, COLORS["pressure_sensor"], "pressure")
    all_meshes.extend(pressure1_meshes)
    
    # -------------------------------------------------------------------------
    # Ground plane (optional - grid effect)
    # -------------------------------------------------------------------------
    total_width = ROOM_SIZE[0] * 2 + ROOM_SPACING
    ground = trimesh.creation.box(extents=[total_width + 4, 0.05, ROOM_SIZE[2] + 4])
    ground.apply_translation([total_width/2, -0.1, ROOM_SIZE[2]/2])
    ground.visual.face_colors = [220, 230, 240, 255]  # Light blue-gray
    all_meshes.append(ground)
    
    return all_meshes


def generate_scene_json(s3_bucket_name="YOUR_TWINMAKER_S3_BUCKET"):
    """Generate the TwinMaker scene.json file."""
    
    # Calculate positions for scene nodes
    room1_center = [4.0, 0, 3.0]
    room2_center = [ROOM_SIZE[0] + ROOM_SPACING + 4.0, 0, 3.0]
    
    scene = {
        "specVersion": "1.0",
        "version": "1",
        "unit": "meters",
        "properties": {},
        "nodes": [
            {
                "name": "room-1",
                "transform": {
                    "position": [0, 0, 0],
                    "rotation": [0, 0, 0],
                    "scale": [1, 1, 1]
                },
                "children": [1, 4],
                "components": [
                    {
                        "type": "ModelRef",
                        "uri": f"s3://{s3_bucket_name}/scene_assets/digital_twin_scene.glb",
                        "modelType": "GLB"
                    }
                ]
            },
            {
                "name": "machine-1",
                "transform": {
                    "position": [3.0, 0.1, 2.5],
                    "rotation": [0, 0, 0],
                    "scale": [1, 1, 1]
                },
                "children": [2],
                "components": [
                    {
                        "type": "Tag",
                        "offset": [0, 2.0, 0],
                        "icon": "iottwinmaker.common.icon:Pump",
                        "valueDataBinding": {
                            "dataBindingContext": {
                                "entityId": "machine-1"
                            }
                        }
                    }
                ]
            },
            {
                "name": "temperature-sensor-1",
                "transform": {
                    "position": [0, 1.6, 0],
                    "rotation": [0, 0, 0],
                    "scale": [0.5, 0.5, 0.5]
                },
                "components": [
                    {
                        "type": "Tag",
                        "offset": [0, 0.5, 0],
                        "icon": "iottwinmaker.common.icon:Thermometer",
                        "valueDataBinding": {
                            "dataBindingContext": {
                                "entityId": "machine-1",
                                "componentName": "temperature-sensor-1",
                                "propertyName": "temperature"
                            }
                        }
                    }
                ]
            },
            {
                "name": "room-2",
                "transform": {
                    "position": [10.0, 0, 0],
                    "rotation": [0, 0, 0],
                    "scale": [1, 1, 1]
                },
                "children": [5],
                "components": []
            },
            {
                "name": "temperature-sensor-2",
                "transform": {
                    "position": [6.0, 0.1, 4.0],
                    "rotation": [0, 0, 0],
                    "scale": [0.5, 0.5, 0.5]
                },
                "components": [
                    {
                        "type": "Tag",
                        "offset": [0, 0.5, 0],
                        "icon": "iottwinmaker.common.icon:Thermometer",
                        "valueDataBinding": {
                            "dataBindingContext": {
                                "entityId": "room-1",
                                "componentName": "temperature-sensor-2",
                                "propertyName": "temperature"
                            }
                        }
                    }
                ]
            },
            {
                "name": "pressure-sensor-1",
                "transform": {
                    "position": [4.0, 0.1, 3.0],
                    "rotation": [0, 0, 0],
                    "scale": [0.5, 0.5, 0.5]
                },
                "components": [
                    {
                        "type": "Tag",
                        "offset": [0, 0.5, 0],
                        "icon": "iottwinmaker.common.icon:Gauge",
                        "valueDataBinding": {
                            "dataBindingContext": {
                                "entityId": "room-2",
                                "componentName": "pressure-sensor-1",
                                "propertyName": "pressure"
                            }
                        }
                    }
                ]
            }
        ],
        "rootNodeIndexes": [0, 3],
        "cameras": [
            {
                "cameraType": "Perspective",
                "fov": 53.13,
                "near": 0.1,
                "far": 1000
            }
        ],
        "rules": {},
        "properties": {
            "environmentPreset": "neutral"
        }
    }
    
    return scene


# =============================================================================
# Main Execution
# =============================================================================

def main():
    print("=" * 60)
    print("Digital Twin Scene Generator for AWS IoT TwinMaker")
    print("=" * 60)
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"\n📁 Output directory: {os.path.abspath(OUTPUT_DIR)}")
    
    # Build scene geometry
    print("\n🔨 Building 3D geometry...")
    meshes = build_scene()
    print(f"   Created {len(meshes)} mesh objects")
    
    # Combine all meshes into a single scene
    print("\n🎨 Combining meshes into scene...")
    combined = trimesh.util.concatenate(meshes)
    
    # Create trimesh Scene
    scene = trimesh.Scene()
    scene.add_geometry(combined, node_name="digital_twin")
    
    # Export as GLB
    glb_path = os.path.join(OUTPUT_DIR, "digital_twin_scene.glb")
    print(f"\n💾 Exporting GLB file: {glb_path}")
    scene.export(glb_path, file_type="glb")
    
    # Get file size
    file_size = os.path.getsize(glb_path) / 1024
    print(f"   ✓ GLB file created ({file_size:.1f} KB)")
    
    # Generate scene.json
    print("\n📄 Generating scene.json...")
    scene_json = generate_scene_json()
    json_path = os.path.join(OUTPUT_DIR, "scene.json")
    with open(json_path, "w") as f:
        json.dump(scene_json, f, indent=2)
    print(f"   ✓ scene.json created")
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ SCENE GENERATION COMPLETE")
    print("=" * 60)
    print(f"""
Generated files:
  1. {glb_path}
     - 3D model with rooms, machine, and sensors
     
  2. {json_path}
     - TwinMaker scene definition
     - Update 's3://YOUR_TWINMAKER_S3_BUCKET' with your bucket

To use with AWS TwinMaker:
  1. Upload both files to your TwinMaker S3 bucket
  2. Update contentLocation in scene.json
  3. Call create_scene API or upload via console
""")


if __name__ == "__main__":
    main()
