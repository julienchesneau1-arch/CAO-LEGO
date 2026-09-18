"use client";

import { useCallback, useEffect, useState } from "react";
import { preparer } from "@/lib/compression";
import { enAttente, mettreEnAttente, reseau, vider } from "@/lib/file-medias";

const CLE_WIFI = "jl_wifi_seulement";

type Libelles = Readonly<Record<string, string>>;

/**
 * « Partager un souvenir » (brief §8.7). Le fichier est préparé dans le
 * téléphone, puis **mis en file** : l'envoi part tout de suite s'il peut, et
 * attend sinon. Rien n'est perdu si le réseau tombe, si l'onglet se ferme ou
 * si le téléphone redémarre.
 *
 * L'indicateur reste discret, comme le demande le brief : un nombre et une
 * phrase, pas une barre de progression qui capte le regard pendant la fête.
 */
export function EnvoyerSouvenir({
  momentCourant,
  suspendu,
  libelles,
}: {
  readonly momentCourant: string | null;
  readonly suspendu: boolean;
  readonly libelles: Libelles;
}) {
  const [attente, setAttente] = useState(0);
  const [wifiSeulement, setWifiSeulement] = useState(false);
  const [message, setMessage] = useState<string | undefined>(undefined);
  const [travaille, setTravaille] = useState(false);

  const rafraichir = useCallback(async () => {
    try {
      setAttente((await enAttente()).length);
    } catch {
      // Stockage bloqué : la file n'existe pas, l'envoi direct marche quand même.
    }
  }, []);

  useEffect(() => {
    try {
      setWifiSeulement(localStorage.getItem(CLE_WIFI) === "1");
    } catch {
      /* navigation privée */
    }
    void rafraichir();
  }, [rafraichir]);

  const envoyerLaFile = useCallback(
    async (forcer: boolean) => {
      setTravaille(true);
      try {
        const resultat = await vider(forcer);
        await rafraichir();
        if (resultat.partis > 0) {
          setMessage(
            (libelles["partis"] ?? "").replace("{nombre}", String(resultat.partis)),
          );
        } else if (resultat.refuses > 0) {
          setMessage(libelles["refuses"]);
        }
      } finally {
        setTravaille(false);
      }
    },
    [libelles, rafraichir],
  );

  /**
   * Reprise : **dès l'ouverture de l'écran**, puis au retour du réseau, au
   * retour dans l'application, et toutes les vingt secondes.
   *
   * La tentative à l'ouverture est celle qui compte le plus : sur iPhone,
   * rien ne peut repartir tant que l'application est fermée, donc la
   * réouverture est le seul moment où la file a une chance de se vider.
   */
  useEffect(() => {
    const reprendre = (): void => void envoyerLaFile(false);
    reprendre();
    window.addEventListener("online", reprendre);
    document.addEventListener("visibilitychange", reprendre);
    const minuterie = setInterval(reprendre, 20_000);
    return () => {
      window.removeEventListener("online", reprendre);
      document.removeEventListener("visibilitychange", reprendre);
      clearInterval(minuterie);
    };
  }, [envoyerLaFile]);

  const choisir = async (evenement: React.ChangeEvent<HTMLInputElement>): Promise<void> => {
    const fichiers = [...(evenement.target.files ?? [])];
    evenement.target.value = "";
    if (fichiers.length === 0) return;

    setTravaille(true);
    setMessage(undefined);
    let refuses = 0;
    try {
      for (const fichier of fichiers) {
        const prepare = await preparer(fichier);
        if ("refus" in prepare) {
          refuses += 1;
          setMessage(libelles[prepare.refus]);
          continue;
        }
        await mettreEnAttente({
          blob: prepare.blob,
          nom: prepare.nom,
          mime: prepare.mime,
          moment: momentCourant,
          largeur: prepare.largeur,
          hauteur: prepare.hauteur,
          duree: prepare.duree,
          wifiSeulement,
          cree: Date.now(),
        });
      }
      await rafraichir();
      if (refuses < fichiers.length) await envoyerLaFile(false);
    } finally {
      setTravaille(false);
    }
  };

  const basculerWifi = (actif: boolean): void => {
    setWifiSeulement(actif);
    try {
      localStorage.setItem(CLE_WIFI, actif ? "1" : "0");
    } catch {
      /* navigation privée */
    }
  };

  const retenus = wifiSeulement && reseau() !== "wifi" && attente > 0;

  return (
    <section aria-labelledby="envoyer" className="flex flex-col gap-5">
      <h2 id="envoyer" className="jl-etiquette">
        {libelles["titre"]}
      </h2>

      {suspendu ? (
        <p className="jl-doux">{libelles["suspendu"]}</p>
      ) : (
        <>
          <label className="jl-cible flex flex-col gap-2">
            <span>{libelles["choisir"]}</span>
            <input
              type="file"
              accept="image/*,video/*"
              multiple
              onChange={(evenement) => void choisir(evenement)}
              className="jl-cible border bg-transparent px-4 py-3"
              style={{ borderColor: "var(--filet)", color: "var(--texte)" }}
            />
          </label>

          <label className="jl-cible flex items-center gap-3">
            <input
              type="checkbox"
              checked={wifiSeulement}
              onChange={(evenement) => basculerWifi(evenement.target.checked)}
            />
            <span>{libelles["wifi"]}</span>
          </label>
        </>
      )}

      <p className="jl-doux text-sm" aria-live="polite">
        {travaille
          ? libelles["travail"]
          : attente === 0
            ? (message ?? libelles["rien"])
            : (libelles["en_attente"] ?? "").replace("{nombre}", String(attente))}
      </p>

      {/*
        Quand on ne peut pas savoir sur quel réseau on est (Safari n'expose
        rien), on ne devine pas : on propose un envoi à la main.
      */}
      {retenus || (attente > 0 && !travaille) ? (
        <button
          type="button"
          onClick={() => void envoyerLaFile(true)}
          className="jl-cible self-start border px-5 py-3"
          style={{ borderColor: "var(--filet)" }}
        >
          {libelles["envoyer_maintenant"]}
        </button>
      ) : null}

      {attente > 0 ? <p className="jl-doux text-sm">{libelles["iphone"]}</p> : null}
    </section>
  );
}
