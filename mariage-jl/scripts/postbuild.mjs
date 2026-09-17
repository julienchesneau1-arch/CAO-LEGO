#!/usr/bin/env node
/**
 * La sortie `standalone` de Next ne contient ni `public/` ni `.next/static` :
 * c'est documenté, et c'est au projet de les copier. Sans cela, le serveur
 * compilé sert des pages sans style ni JavaScript — ce qui, ici, faisait
 * échouer tous les parcours d'un coup sans dire pourquoi.
 *
 * Ce script tourne après chaque `pnpm build`, pour que la sortie soit
 * toujours exécutable telle quelle (tests, captures, image Docker).
 */
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const racine = join(dirname(fileURLToPath(import.meta.url)), "..");
const standalone = join(racine, ".next", "standalone");

if (!existsSync(standalone)) {
  console.log("Pas de sortie standalone : rien à copier.");
  process.exit(0);
}

const copies = [
  [join(racine, ".next", "static"), join(standalone, ".next", "static")],
  [join(racine, "public"), join(standalone, "public")],
];

for (const [source, destination] of copies) {
  if (!existsSync(source)) continue;
  mkdirSync(dirname(destination), { recursive: true });
  cpSync(source, destination, { recursive: true });
  console.log(`copié : ${source.replace(racine, ".")} → ${destination.replace(racine, ".")}`);
}
