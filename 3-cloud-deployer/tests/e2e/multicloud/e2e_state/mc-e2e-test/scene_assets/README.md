# 3D Scene Assets for Digital Twin

This folder contains 3D visualization assets for the digital twin hierarchy.

## Directory Structure

```
scene_assets/
├── scene_preview.png           # Preview image of the scene
├── aws/
│   ├── scene.glb               # AWS TwinMaker GLB file
│   └── scene.json              # AWS TwinMaker scene definition
└── azure/
    ├── scene.glb               # Azure GLB file (same model)
    └── 3DScenesConfiguration.json  # Azure 3D Scenes Studio config
```

---

## Creating & Editing 3D Assets

### GLB/glTF 3D Models

| Tool | Type | Cost | Best For |
|------|------|------|----------|
| **[Blender](https://www.blender.org/)** | Desktop | Free & Open Source | Full 3D modeling, animation, texturing |
| **[Tinkercad](https://www.tinkercad.com/)** | Online | Free | Beginners, simple shapes |
| **[gltfeditor.com](https://gltfeditor.com/)** | Online | Free | Quick edits, material changes |
| **[model-viewer Editor](https://modelviewer.dev/editor/)** | Online | Free | Preview and tweak materials |
| **[RauGen GLB Editor](https://raugen.com/editor/)** | Online | Free | Customize colors, textures, logos |

**Recommended:** [Blender](https://www.blender.org/) is the industry standard for free 3D modeling. 
It can import/export GLB directly via File → Export → glTF 2.0.

### Scene Configuration Files

**You don't need to edit scene.json or 3DScenesConfiguration.json manually!**

Both AWS and Azure provide **visual editors** that generate these files automatically:

| Provider | Visual Editor | How to Access |
|----------|---------------|---------------|
| **AWS TwinMaker** | Scene Composer | AWS Console → IoT TwinMaker → Scenes → Create Scene |
| **Azure ADT** | 3D Scenes Studio | Azure Portal → Digital Twins → 3D Scenes (preview) |

#### AWS Workflow
1. Terraform uploads your GLB to the TwinMaker S3 bucket
2. Open **AWS Console → IoT TwinMaker → Scenes**
3. Use the **Scene Composer** to:
   - Import your 3D model
   - Position objects in the 3D space
   - Bind data from your digital twin entities
4. The console saves `scene.json` automatically

#### Azure Workflow
1. Terraform uploads your GLB to Azure Blob Storage
2. Open **Azure Portal → Digital Twins → 3D Scenes (preview)**
3. Use the **3D Scenes Studio** to:
   - Import your 3D model
   - Map 3D objects to digital twin IDs
   - Define visual behaviors (color rules)
4. The portal generates `3DScenesConfiguration.json` automatically

---

## AWS IoT TwinMaker

### Files
- `aws/scene.glb` - Binary glTF 3D model (46 KB)
- `aws/scene.json` - TwinMaker scene definition with node hierarchy

### Automatic Deployment (via Terraform)

When `needs_3d_model = true`, Terraform automatically:
1. Uploads `scene.glb` to the TwinMaker S3 bucket
2. Uploads `scene.json` to the same bucket
3. Creates the TwinMaker scene via `awscc_iottwinmaker_scene`

### Manual Upload (if needed)
```bash
aws s3 cp aws/scene.glb s3://YOUR_BUCKET/scene_assets/
aws s3 cp aws/scene.json s3://YOUR_BUCKET/scene_assets/
```

---

## Azure Digital Twins (3D Scenes Studio)

### Files
- `azure/scene.glb` - Binary glTF 3D model (46 KB)
- `azure/3DScenesConfiguration.json` - Scene configuration with elements and behaviors

### Automatic Deployment (via Terraform)

When `needs_3d_model = true`, Terraform automatically:
1. Creates a `3dscenes` blob container
2. Uploads `scene.glb` to the container
3. Uploads `3DScenesConfiguration.json` to the container

### Manual Configuration
After deployment, link the container to 3D Scenes Studio:
1. Navigate to [3D Scenes Studio](https://explorer.digitaltwins.azure.net/3dscenes)
2. Connect to your Azure Digital Twins instance
3. Set the storage container URL (output by Terraform)
4. The scene will auto-load from the configuration file

### Configuration Structure

The `3DScenesConfiguration.json` defines:
- **Scenes**: The 3D view with linked assets and elements
- **Elements**: Mappings between 3D objects and digital twin IDs
- **Behaviors**: Visual rules (color coding based on sensor values)
- **Layers**: Visibility groups for filtering sensors

---

## Scene Contents

The 3D scene represents:

| Entity | Type | Sensors |
|--------|------|---------|
| **room-1** | Room | temperature-sensor-2 (standalone) |
| **machine-1** | Machine (in room-1) | temperature-sensor-1 (on top) |
| **room-2** | Room | pressure-sensor-1 |

### Visual Behaviors

**Temperature Sensors:**
- 🟢 Green: 0-30°C (normal)
- 🟠 Orange: 30-50°C (warning)
- 🔴 Red: >50°C (critical)

**Pressure Sensor:**
- 🔵 Blue: 0-800 hPa (low)
- 🟢 Green: 800-1200 hPa (normal)
- 🔴 Red: >1200 hPa (high)
