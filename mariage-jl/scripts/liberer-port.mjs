/**
 * Libère un port TCP laissé occupé par une exécution interrompue.
 * Sans cela, un serveur orphelin fait échouer les parcours et la mesure
 * Lighthouse avec un message qui ne dit pas la cause.
 */
import { readFileSync, readdirSync, readlinkSync } from "node:fs";

export function libererPort(port) {
  const cible = Number(port).toString(16).toUpperCase().padStart(4, "0");
  const inodes = new Set();
  for (const ligne of readFileSync("/proc/net/tcp", "utf8").split("\n").slice(1)) {
    const champs = ligne.trim().split(/\s+/);
    if (champs.length > 9 && champs[1]?.split(":")[1] === cible && champs[3] === "0A") {
      inodes.add(champs[9]);
    }
  }
  if (inodes.size === 0) return false;

  for (const pid of readdirSync("/proc").filter((nom) => /^\d+$/.test(nom))) {
    let descripteurs = [];
    try {
      descripteurs = readdirSync(`/proc/${pid}/fd`);
    } catch {
      continue;
    }
    for (const fd of descripteurs) {
      try {
        const lien = readlinkSync(`/proc/${pid}/fd/${fd}`);
        const inode = /^socket:\[(\d+)\]$/.exec(lien)?.[1];
        if (inode !== undefined && inodes.has(inode)) {
          process.kill(Number(pid), "SIGKILL");
          console.log(`Port ${port} libéré (processus ${pid} arrêté).`);
          return true;
        }
      } catch {
        /* descripteur volatile */
      }
    }
  }
  return false;
}
