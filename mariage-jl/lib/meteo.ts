import "server-only";
import { env } from "./env";

/**
 * Météo du domaine à sept jours (brief §0 bis, « Météo J-7 »). Open-Meteo :
 * gratuit, sans compte et sans clé — donc sans dépense et sans secret à
 * garder. Les coordonnées ne sont **pas** devinées : tant que la question
 * V1-07 est ouverte, la fonction renvoie `undefined` et l'écran se contente
 * de ne rien dire.
 *
 * Aucune donnée personnelle ne sort d'ici : on demande la météo d'un lieu,
 * jamais celle de l'invité.
 */
export type Meteo = {
  readonly jour: string;
  readonly minimum: number;
  readonly maximum: number;
  readonly pluieMm: number;
  readonly code: number;
};

/** « latitude,longitude » du domaine, une fois la question V1-07 répondue. */
const endroit = (): string | undefined => env().JL_METEO_COORDONNEES;

type Reponse = {
  daily?: {
    time?: ReadonlyArray<string>;
    temperature_2m_min?: ReadonlyArray<number>;
    temperature_2m_max?: ReadonlyArray<number>;
    precipitation_sum?: ReadonlyArray<number>;
    weather_code?: ReadonlyArray<number>;
  };
};

export function coordonneesConnues(): boolean {
  return /^-?\d+(\.\d+)?,-?\d+(\.\d+)?$/.test(endroit() ?? "");
}

/**
 * Prévision du jour du mariage, ou `undefined` si elle n'est pas disponible :
 * coordonnées inconnues, date hors de la fenêtre de prévision, réseau coupé.
 * Un écran de mariage ne doit jamais tomber parce qu'un service tiers tousse.
 */
export async function previsionDuJour(jour: Date): Promise<Meteo | undefined> {
  if (!coordonneesConnues()) return undefined;
  const [latitude, longitude] = (endroit() ?? "").split(",");
  const date = jour.toISOString().slice(0, 10);

  const url = new URL("https://api.open-meteo.com/v1/forecast");
  url.searchParams.set("latitude", latitude ?? "");
  url.searchParams.set("longitude", longitude ?? "");
  url.searchParams.set(
    "daily",
    "temperature_2m_min,temperature_2m_max,precipitation_sum,weather_code",
  );
  url.searchParams.set("timezone", "Europe/Paris");
  url.searchParams.set("start_date", date);
  url.searchParams.set("end_date", date);

  try {
    // Le cache d'une heure suffit : la prévision à sept jours ne change pas
    // de minute en minute, et cela évite d'appeler le service à chaque visite.
    const reponse = await fetch(url, { next: { revalidate: 3600 }, signal: AbortSignal.timeout(4000) });
    if (!reponse.ok) return undefined;
    const donnees = (await reponse.json()) as Reponse;
    const jours = donnees.daily;
    const minimum = jours?.temperature_2m_min?.[0];
    const maximum = jours?.temperature_2m_max?.[0];
    if (minimum === undefined || maximum === undefined) return undefined;
    return {
      jour: jours?.time?.[0] ?? date,
      minimum,
      maximum,
      pluieMm: jours?.precipitation_sum?.[0] ?? 0,
      code: jours?.weather_code?.[0] ?? 0,
    };
  } catch {
    return undefined;
  }
}

/** Trois familles suffisent : on ne fait pas un bulletin, on habille quelqu'un. */
export function famille(code: number): "soleil" | "nuages" | "pluie" | "orage" {
  if (code >= 95) return "orage";
  if (code >= 51) return "pluie";
  if (code >= 2) return "nuages";
  return "soleil";
}
