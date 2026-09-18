import Link from "next/link";
import { cookies } from "next/headers";
import { CarteAFaire } from "@/components/CarteAFaire";
import { ChecklistSemaine } from "@/components/ChecklistSemaine";
import { Maintenant } from "@/components/Maintenant";
import { Merci } from "@/components/Merci";
import { derniereAnnonce } from "@/lib/annonces";
import { CompteARebours } from "@/components/CompteARebours";
import { FiletsEtapes } from "@/components/FiletsEtapes";
import { Film } from "@/components/Film";
import { PremierLancement } from "@/components/PremierLancement";
import { Signature } from "@/components/Signature";
import { restant } from "@/lib/compte";
import { env } from "@/lib/env";
import { aRepondu, foyerCourant, parametres, periodeCourante } from "@/lib/foyer";
import {
  COOKIE_LANGUE,
  LANGUE_DEFAUT,
  dictionnaire,
  estLangue,
  formater,
  formaterDate,
} from "@/lib/i18n";
import { echeances } from "@/lib/apres";
import { contenus } from "@/lib/contenus";
import { etatJournee } from "@/lib/journee";
import { galerie } from "@/lib/medias";
import { previsionDuJour, famille } from "@/lib/meteo";
import { etapesFranchies } from "@/lib/periode";

export const dynamic = "force-dynamic";

/** Les six étapes de la checklist de la semaine J (brief §8.5). */
const ETAPES_SEMAINE = [
  "tenue",
  "trajet",
  "hebergement",
  "table",
  "ecran_accueil",
  "batterie",
] as const;

/**
 * Accueil (brief §7 et §8.1). Le contenu suit la période : « Avant » montre
 * le film, le compte à rebours et la carte « À faire » ; « Semaine J » y
 * ajoute la checklist sereine et la météo du jour ; « Jour J » devient
 * « Maintenant » (§8.6). La période « Après » arrive en V4 : l'écran le dit
 * plutôt que d'afficher une page vide.
 */
export default async function Accueil() {
  const magasin = await cookies();
  const valeurLangue = magasin.get(COOKIE_LANGUE)?.value;
  const langue = estLangue(valeurLangue) ? valeurLangue : LANGUE_DEFAUT;
  const t = dictionnaire(langue);

  const maintenant = new Date();
  const parametresJournee = await parametres();
  const periode = await periodeCourante(maintenant);
  const foyer = await foyerCourant();
  const repondu = foyer === undefined ? false : await aRepondu(foyer.id);
  const annonce = await derniereAnnonce(langue);

  const etapes = etapesFranchies(maintenant, parametresJournee.date_mariage, repondu).map(
    (etape) => ({
      libelle: t.accueil[`etape_${etape.etape}` as const],
      franchie: etape.franchie,
    }),
  );

  const bienvenue =
    foyer === undefined
      ? t.accueil.bienvenue_generique
      : formater(t.accueil.bienvenue, { foyer: foyer.label_public });

  const limite = parametresJournee.date_limite_reponse;
  const action = repondu
    ? { texte: t.accueil.a_faire_rien }
    : {
        texte:
          limite === null
            ? t.accueil.a_faire_repondre
            : formater(t.accueil.a_faire_repondre_avant, {
                date: formaterDate(limite, langue),
              }),
        lien: "/reponse",
      };

  const { JL_FILM_URL, JL_FILM_POSTER_URL } = env();

  // « Maintenant » et la météo ne sont calculés que là où ils servent : le
  // jour J n'appelle pas Open-Meteo, et la période « Avant » ne lit pas
  // l'état de la journée.
  const journee = periode === "jour" ? await etatJournee(maintenant) : undefined;
  const meteo =
    periode === "semaine" ? await previsionDuJour(parametresJournee.date_mariage) : undefined;

  // Période « Après » : le mot des mariés, quelques vignettes, et les dates
  // de fin — qui viennent des mêmes expressions que les purges.
  const apres =
    periode === "apres"
      ? await (async () => {
          const [blocs, vignettes, dates] = await Promise.all([
            contenus(langue),
            galerie({
              limite: 9,
              ...(foyer === undefined ? {} : { foyer: foyer.id }),
            }),
            echeances(),
          ]);
          const bloc = blocs["apres.merci"];
          const enAttente =
            bloc === undefined ||
            bloc.texte.trim() === "" ||
            bloc.texte.includes("[À COMPLÉTER]") ||
            bloc.texte.includes("[TO BE COMPLETED]");
          return {
            message: enAttente ? null : (bloc?.texte ?? null),
            vignettes: vignettes.filter((m) => m.kind === "photo").map((m) => m.id),
            dates,
          };
        })()
      : undefined;

  return (
    <>
      <PremierLancement
        langueCourante={langue}
        libelles={{
          passer: t.lancement.passer,
          suivant: t.lancement.suivant,
          ecran1: t.lancement.ecran1,
          ecran3_titre: t.lancement.ecran3_titre,
          ecran3_texte: t.lancement.ecran3_texte,
          bienvenue,
          confort: {
            titre: t.confort.titre,
            taille: t.confort.taille,
            tailles: {
              normale: t.confort.taille_normale,
              grande: t.confort.taille_grande,
              "tres-grande": t.confort.taille_tres_grande,
            },
            papier: t.confort.papier,
            mouvement: t.confort.mouvement,
            langue: t.confort.langue,
            bascule: t.langue.bascule,
          },
        }}
      />

      <main className="mx-auto flex max-w-2xl flex-col gap-12 px-6 py-14">
        {/*
          Le jour J, la date ne renseigne plus personne : la place revient au
          moment en cours (§8.6). L'en-tête s'allège, sans disparaître.
        */}
        <header className="flex flex-col gap-6">
          <Signature mention={t.accueil.signature} titreAccessible="Julien & Lauriane" />
          {periode === "jour" ? null : (
            <p className="jl-titre text-4xl tracking-[0.12em]">{t.accueil.date}</p>
          )}
          <p className="jl-doux">{t.accueil.lieu}</p>
          <p>{bienvenue}</p>
        </header>

        <hr className="jl-filet" />

        {/* La dernière annonce, s'il y en a une : rien ne clignote, rien ne
            s'impose — elle est simplement là, au-dessus du reste. */}
        {annonce === undefined ? null : (
          <section aria-labelledby="derniere-annonce" className="flex flex-col gap-2">
            <h2 id="derniere-annonce" className="jl-etiquette">
              {t.annonces.derniere}
            </h2>
            <p className="jl-titre text-xl">{annonce.texte}</p>
            <Link
              href="/annonces"
              className="jl-cible jl-etiquette flex items-center underline decoration-1 underline-offset-8"
            >
              {t.annonces.lien}
            </Link>
          </section>
        )}

        {periode === "jour" && journee !== undefined ? (
          <Maintenant
            etat={journee}
            langue={langue}
            libelles={{ maintenant: t.maintenant, adresse: t.infos.adresse }}
          />
        ) : null}

        {periode === "avant" || periode === "semaine" ? (
          <>
            <CompteARebours
              cibleIso={parametresJournee.date_mariage.toISOString()}
              initial={restant(parametresJournee.date_mariage.getTime(), maintenant.getTime())}
              libelles={{
                titre: t.accueil.compte_titre,
                jours: t.accueil.compte_jours,
                heures: t.accueil.compte_heures,
                minutes: t.accueil.compte_minutes,
                secondes: t.accueil.compte_secondes,
              }}
            />
            <FiletsEtapes etapes={etapes} />
            <CarteAFaire
              titre={t.accueil.a_faire}
              action={action.texte}
              {...(action.lien === undefined ? {} : { lien: action.lien })}
            />
            <Film
              {...(JL_FILM_URL === undefined || JL_FILM_URL === "" ? {} : { url: JL_FILM_URL })}
              {...(JL_FILM_POSTER_URL === undefined || JL_FILM_POSTER_URL === ""
                ? {}
                : { poster: JL_FILM_POSTER_URL })}
              libelles={{
                titre: t.accueil.film_titre,
                attente: t.accueil.film_attente,
                lire: t.accueil.film_lire,
              }}
            />
            {periode === "semaine" ? (
              <>
                <hr className="jl-filet" />
                <ChecklistSemaine
                  etapes={ETAPES_SEMAINE.map((etape) => ({
                    cle: etape,
                    libelle: t.semaine[etape],
                  }))}
                  libelles={{
                    titre: t.semaine.checklist,
                    faite: t.semaine.faite,
                    locale: t.semaine.locale,
                  }}
                />
                <section aria-labelledby="meteo" className="flex flex-col gap-2">
                  <h2 id="meteo" className="jl-etiquette">
                    {t.semaine.meteo}
                  </h2>
                  {meteo === undefined ? (
                    <p className="jl-doux">{t.semaine.meteo_absente}</p>
                  ) : (
                    <>
                      <p className="jl-titre text-xl tabular-nums">
                        {formater(t.semaine.meteo_temperatures, {
                          min: String(Math.round(meteo.minimum)),
                          max: String(Math.round(meteo.maximum)),
                        })}
                      </p>
                      <p className="jl-doux">
                        {
                          {
                            soleil: t.semaine.meteo_soleil,
                            nuages: t.semaine.meteo_nuages,
                            pluie: t.semaine.meteo_pluie_famille,
                            orage: t.semaine.meteo_orage,
                          }[famille(meteo.code)]
                        }
                      </p>
                      {meteo.pluieMm <= 0 ? null : (
                        <p className="jl-doux tabular-nums">
                          {formater(t.semaine.meteo_pluie, {
                            mm: String(Math.round(meteo.pluieMm)),
                          })}
                        </p>
                      )}
                    </>
                  )}
                </section>
              </>
            ) : null}
          </>
        ) : null}

        {periode === "apres" && apres !== undefined ? (
          <Merci
            message={apres.message}
            vignettes={apres.vignettes}
            echeances={apres.dates}
            langue={langue}
            libelles={t.merci}
            reconnu={foyer !== undefined}
          />
        ) : null}

        <hr className="jl-filet" />

        <Link
          href="/le-texte"
          className="jl-etiquette jl-cible flex items-center underline decoration-1 underline-offset-8"
        >
          {t.texte.lien}
        </Link>

        <Link
          href="/promesse"
          className="jl-etiquette jl-cible flex items-center underline decoration-1 underline-offset-8"
        >
          {t.promesse.lien}
        </Link>

        {foyer === undefined ? null : (
          <Link
            href="/partager"
            className="jl-etiquette jl-cible flex items-center underline decoration-1 underline-offset-8"
          >
            {t.accueil.partager_lien}
          </Link>
        )}
      </main>
    </>
  );
}
