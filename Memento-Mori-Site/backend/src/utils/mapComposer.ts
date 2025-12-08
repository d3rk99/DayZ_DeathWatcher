import sharp from 'sharp';
import fs from 'fs';
import path from 'path';
import { APP_CONFIG } from '../config';

export interface PlacementRenderInput {
  storage_path: string;
  x_norm: number;
  y_norm: number;
  scale: number;
  rotation_deg: number;
  width_px: number;
  height_px: number;
}

const ensureDir = (dir: string) => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
};

export const composeMap = async (
  mapName: string,
  placements: PlacementRenderInput[],
): Promise<{ outputPath: string; version: number }> => {
  ensureDir(APP_CONFIG.mapAssets.currentDir);
  ensureDir(APP_CONFIG.mapAssets.templateDir);
  const basePath = path.join(APP_CONFIG.mapAssets.templateDir, `${mapName}.png`);
  if (!fs.existsSync(basePath)) {
    await sharp({ create: { width: 2048, height: 2048, channels: 4, background: '#1e1e1e' } })
      .png()
      .toFile(basePath);
  }
  const base = sharp(basePath);
  const meta = await base.metadata();
  const overlays = await Promise.all(
    placements.map(async (p) => {
      const buffer = await sharp(p.storage_path)
        .resize({
          width: Math.round(p.width_px * p.scale),
          height: Math.round(p.height_px * p.scale),
          fit: 'contain',
        })
        .rotate(p.rotation_deg)
        .png()
        .toBuffer();
      const left = Math.round((meta.width || 0) * p.x_norm - (p.width_px * p.scale) / 2);
      const top = Math.round((meta.height || 0) * p.y_norm - (p.height_px * p.scale) / 2);
      return { input: buffer, top, left } as sharp.OverlayOptions;
    })
  );

  const existingVersions = fs
    .readdirSync(APP_CONFIG.mapAssets.currentDir)
    .filter((f) => f.startsWith(`${mapName}_v`) && f.endsWith('.png'));
  const nextVersion = existingVersions.length + 1;
  const outputPath = path.join(
    APP_CONFIG.mapAssets.currentDir,
    `${mapName}_v${String(nextVersion).padStart(3, '0')}.png`,
  );

  await base.composite(overlays).png().toFile(outputPath);

  return { outputPath, version: nextVersion };
};
