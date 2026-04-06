# Manual Steps: 3D Scene Setup After Deployment

After Terraform deploys the infrastructure with `needs_3d_model = true`, the GLB model and scene configuration files are uploaded automatically. The following manual steps are required to complete the 3D scene setup.

## AWS TwinMaker

1. Open **AWS Console → IoT TwinMaker → Scenes**
2. Use the **Scene Composer** to:
   - Import the 3D model (already in the TwinMaker S3 bucket)
   - Position objects in the 3D space
   - Bind data from digital twin entities to 3D objects
3. The console saves `scene.json` automatically

## Azure Digital Twins

1. Navigate to [3D Scenes Studio](https://explorer.digitaltwins.azure.net/3dscenes)
2. Connect to your Azure Digital Twins instance
3. Set the storage container URL (output by Terraform as part of deployment outputs)
4. The scene will auto-load from the `3DScenesConfiguration.json`
5. Use **3D Scenes Studio** to:
   - Map 3D objects to digital twin IDs
   - Define visual behaviors (color rules based on sensor thresholds)

## Visual Behavior Examples

| Sensor | Green | Orange | Red |
|--------|-------|--------|-----|
| Temperature | 0–30°C | 30–50°C | >50°C |
| Pressure | 800–1200 hPa | — | >1200 hPa |

## File Reference

Scene assets are located in the user's project at `scene_assets/`:
```
scene_assets/
├── scene_preview.png
├── aws/
│   ├── scene.glb
│   └── scene.json
└── azure/
    ├── scene.glb
    └── 3DScenesConfiguration.json
```
