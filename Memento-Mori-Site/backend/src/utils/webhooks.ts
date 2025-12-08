import { APP_CONFIG } from '../config';

const sendWebhook = async (url: string | undefined, payload: any) => {
  if (!url) return;
  try {
    await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    console.warn('Webhook send failed', err);
  }
};

export const notifyPatchNote = async (title: string) =>
  sendWebhook(APP_CONFIG.discordWebhook.patchNotes, {
    content: `New patch note posted: **${title}**`,
  });

export const notifyMapExport = async (versionLabel: string) =>
  sendWebhook(APP_CONFIG.discordWebhook.map, {
    content: `New map layer exported: ${versionLabel}`,
  });

export const notifyWhitelist = async (discordTag: string, status: string) =>
  sendWebhook(APP_CONFIG.discordWebhook.whitelist, {
    content: `Whitelist update for ${discordTag}: ${status}`,
  });
