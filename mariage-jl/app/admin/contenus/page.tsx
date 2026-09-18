import {
  BLOCS_AVEC_LIEN,
  type BlocAdmin,
  type FaqAdmin,
  type HebergementAdmin,
  blocsAdmin,
  faqAdmin,
  hebergementsAdmin,
  momentsAdmin,
  resteACompleter,
} from "@/lib/contenus-admin";
import { parametres } from "@/lib/foyer";
import { formater, formaterDate, type Langue } from "@/lib/i18n";
import { langueEtTextes } from "@/lib/page-commune";

export const dynamic = "force-dynamic";

const SECTIONS = ["journee", "moments", "infos", "faq", "hebergements"] as const;
type Section = (typeof SECTIONS)[number];

const estSection = (valeur: string | undefined): valeur is Section =>
  valeur !== undefined && (SECTIONS as readonly string[]).includes(valeur);

const BORDURE = { borderColor: "var(--filet)" };
// `jl-cible` garantit les 48 px de hauteur exigés par le brief §12, y compris
// sur les champs d'une seule ligne.
const CHAMP = "jl-cible border bg-transparent px-4 py-3";
const STYLE_CHAMP = { ...BORDURE, color: "var(--texte)" };
const BOUTON = "jl-cible border px-5 py-3";

const jourIso = (date: Date | null): string =>
  date === null ? "" : date.toISOString().slice(0, 10);

const enAttente = (texte: string | null): boolean =>
  texte === null ||
  texte.trim() === "" ||
  texte.includes("[À COMPLÉTER]") ||
  texte.includes("[TO BE COMPLETED]");

/** Libellé + champ : la même structure partout, pour que l'œil ne cherche pas. */
function Champ({
  libelle,
  children,
  aide,
}: {
  readonly libelle: string;
  readonly children: React.ReactNode;
  readonly aide?: string;
}) {
  return (
    <label className="flex flex-col gap-2">
      <span className="jl-etiquette">{libelle}</span>
      {children}
      {aide === undefined ? null : <span className="jl-doux text-sm">{aide}</span>}
    </label>
  );
}

/**
 * Liste d'éléments à écrire : un lien par élément, avec son état. Empiler les
 * dix-huit formulaires de la FAQ donnait un écran de dix-sept mille pixels,
 * impraticable au téléphone ; on choisit d'abord, on écrit ensuite.
 */
function Liste({
  section,
  elements,
  ajout,
  libelleModifier,
}: {
  readonly section: Section;
  readonly elements: ReadonlyArray<{
    readonly cle: string;
    readonly titre: string;
    readonly etat: string;
    readonly attente: boolean;
  }>;
  readonly ajout?: { readonly cle: string; readonly libelle: string };
  readonly libelleModifier: string;
}) {
  return (
    <ul className="flex flex-col">
      {elements.map((element) => (
        <li key={element.cle} className="flex flex-col">
          <a
            href={`/admin/contenus?section=${section}&element=${encodeURIComponent(element.cle)}`}
            className="jl-cible flex items-center justify-between gap-4 py-3"
            aria-label={`${libelleModifier} — ${element.titre}`}
          >
            <span className="min-w-0 flex-1">{element.titre}</span>
            <span
              className="jl-etiquette shrink-0"
              style={{ color: element.attente ? "var(--texte)" : "var(--doux)" }}
            >
              {element.etat}
            </span>
          </a>
          <hr className="jl-filet" />
        </li>
      ))}
      {ajout === undefined ? null : (
        <li className="pt-4">
          <a
            href={`/admin/contenus?section=${section}&element=${ajout.cle}`}
            className={`${BOUTON} inline-flex items-center`}
            style={BORDURE}
          >
            {ajout.libelle}
          </a>
        </li>
      )}
    </ul>
  );
}

async function RetourListe({ section }: { readonly section: Section }) {
  const { t } = await langueEtTextes();
  return (
    <a
      href={`/admin/contenus?section=${section}`}
      className="jl-cible jl-etiquette flex items-center underline decoration-1 underline-offset-8"
    >
      {t.admin_contenus.retour_liste}
    </a>
  );
}

/**
 * Contenus (brief §14). Tout ce que le brief marque « [À COMPLÉTER] » se
 * remplit ici, sans SQL. Un formulaire n'écrit qu'un élément : une saisie au
 * téléphone ne peut pas écraser ce qui vient d'être écrit ailleurs.
 */
export default async function PageAdminContenus({
  searchParams,
}: {
  readonly searchParams: Promise<{ section?: string; element?: string; etat?: string }>;
}) {
  const { langue, t } = await langueEtTextes();
  const { section: brute, element, etat } = await searchParams;
  const section: Section = estSection(brute) ? brute : "journee";
  const reste = await resteACompleter();

  return (
    <main className="flex flex-col gap-8">
      <h1 className="jl-titre text-2xl">{t.admin_contenus.titre}</h1>
      <p className="jl-doux">{t.admin_contenus.intro}</p>
      <p aria-live="polite">
        {reste === 0
          ? t.admin_contenus.complet
          : formater(t.admin_contenus.reste, { nombre: String(reste) })}
      </p>

      <nav aria-label={t.admin_contenus.titre} className="flex flex-wrap gap-x-5 gap-y-2">
        {SECTIONS.map((cle) => (
          <a
            key={cle}
            href={`/admin/contenus?section=${cle}`}
            aria-current={cle === section ? "page" : undefined}
            className="jl-cible jl-etiquette flex items-center"
            style={{ color: cle === section ? "var(--texte)" : "var(--doux)" }}
          >
            {t.admin_contenus[`onglet_${cle}`]}
          </a>
        ))}
      </nav>

      {etat === "enregistre" || etat === "supprime" ? (
        <p aria-live="polite" className="jl-doux">
          {etat === "supprime" ? t.admin_contenus.supprime : t.admin_contenus.enregistre}
        </p>
      ) : null}
      {etat === "erreur" || etat === "lien" ? (
        <p role="alert" className="border p-4" style={BORDURE}>
          {etat === "lien" ? t.admin_contenus.lien_refuse : t.admin_contenus.erreur}
        </p>
      ) : null}

      <hr className="jl-filet" />

      {section === "journee" ? <Journee /> : null}
      {section === "moments" ? <Moments langue={langue} choisi={element} /> : null}
      {section === "infos" ? <Infos choisi={element} /> : null}
      {section === "faq" ? <Faq choisi={element} /> : null}
      {section === "hebergements" ? <Hebergements choisi={element} /> : null}
    </main>
  );
}

// ------------------------------------------------------------------ Journée

async function Journee() {
  const { langue, t } = await langueEtTextes();
  const jour = await parametres();

  return (
    <section aria-labelledby="journee" className="flex flex-col gap-6">
      <h2 id="journee" className="jl-titre text-xl">
        {t.admin_contenus.onglet_journee}
      </h2>
      <div className="flex flex-col gap-2">
        <span className="jl-etiquette">{t.admin_contenus.date_mariage}</span>
        <p className="jl-titre text-xl">{formaterDate(jour.date_mariage, langue)}</p>
        <span className="jl-doux text-sm">{t.admin_contenus.date_mariage_fixe}</span>
      </div>
      <form method="post" action="/admin/contenus/journee" className="flex flex-col gap-5">
        <Champ libelle={t.admin_contenus.date_limite} aide={t.admin_contenus.date_limite_aide}>
          <input
            type="date"
            name="date_limite"
            defaultValue={jourIso(jour.date_limite_reponse)}
            className={CHAMP}
            style={STYLE_CHAMP}
          />
        </Champ>
        {/*
          Le sélecteur de date suit la langue du téléphone, pas celle de la
          page : on redit donc en clair ce qui est enregistré, pour qu'un
          15/04 ne soit jamais lu comme un 4 avril.
        */}
        {jour.date_limite_reponse === null ? null : (
          <p className="jl-doux text-sm">{formaterDate(jour.date_limite_reponse, langue)}</p>
        )}
        <button type="submit" className={`${BOUTON} self-start`} style={BORDURE}>
          {t.admin_contenus.enregistrer}
        </button>
      </form>
    </section>
  );
}

// ------------------------------------------------------------------ Moments

async function Moments({
  langue,
  choisi,
}: {
  readonly langue: Langue;
  readonly choisi: string | undefined;
}) {
  const { t } = await langueEtTextes();
  const liste = await momentsAdmin(langue);
  const moment = liste.find((candidat) => candidat.id === choisi);

  if (moment === undefined) {
    return (
      <>
        <p className="jl-doux text-sm">{t.admin_contenus.nom_fixe}</p>
        <Liste
          section="moments"
          libelleModifier={t.admin_contenus.modifier}
          elements={liste.map((candidat) => ({
            cle: candidat.id,
            titre: `${candidat.id} · ${candidat.nom}`,
            etat: candidat.debut ?? t.admin_contenus.etat_a_completer,
            attente: candidat.debut === null,
          }))}
        />
      </>
    );
  }

  return (
    <section aria-labelledby="moment" className="flex flex-col gap-5">
      <RetourListe section="moments" />
      <h2 id="moment" className="jl-titre text-xl">
        <span className="jl-numero">{moment.id}</span> {moment.nom} · {moment.genre}
      </h2>
      {moment.shift_minutes === 0 ? null : (
        <p className="jl-doux text-sm">
          {formater(t.admin_contenus.decalage, { minutes: String(moment.shift_minutes) })}
        </p>
      )}
      <form method="post" action="/admin/contenus/moment" className="flex flex-col gap-5">
        <input type="hidden" name="id" value={moment.id} />
        <div className="flex gap-5">
          <Champ libelle={t.admin_contenus.heure_debut}>
            <input
              type="time"
              name="debut"
              defaultValue={moment.debut ?? ""}
              className={CHAMP}
              style={STYLE_CHAMP}
            />
          </Champ>
          <Champ libelle={t.admin_contenus.heure_fin}>
            <input
              type="time"
              name="fin"
              defaultValue={moment.fin ?? ""}
              className={CHAMP}
              style={STYLE_CHAMP}
            />
          </Champ>
        </div>
        <p className="jl-doux text-sm">{t.admin_contenus.heure_aide}</p>
        <Champ libelle={t.admin_contenus.lieu}>
          <input
            type="text"
            name="place"
            maxLength={200}
            defaultValue={moment.place ?? ""}
            className={CHAMP}
            style={STYLE_CHAMP}
          />
        </Champ>
        <Champ libelle={t.admin_contenus.ambiance_fr}>
          <input
            type="text"
            name="ambience_fr"
            maxLength={200}
            defaultValue={moment.ambience_fr ?? ""}
            className={CHAMP}
            style={STYLE_CHAMP}
          />
        </Champ>
        <Champ libelle={t.admin_contenus.ambiance_en}>
          <input
            type="text"
            name="ambience_en"
            maxLength={200}
            defaultValue={moment.ambience_en ?? ""}
            className={CHAMP}
            style={STYLE_CHAMP}
          />
        </Champ>
        <Champ libelle={t.admin_contenus.detail_fr}>
          <textarea
            name="detail_fr"
            rows={4}
            maxLength={1000}
            defaultValue={moment.detail_fr ?? ""}
            className={CHAMP}
            style={STYLE_CHAMP}
          />
        </Champ>
        <Champ libelle={t.admin_contenus.detail_en}>
          <textarea
            name="detail_en"
            rows={4}
            maxLength={1000}
            defaultValue={moment.detail_en ?? ""}
            className={CHAMP}
            style={STYLE_CHAMP}
          />
        </Champ>
        <button type="submit" className={`${BOUTON} self-start`} style={BORDURE}>
          {t.admin_contenus.enregistrer}
        </button>
      </form>
    </section>
  );
}

// -------------------------------------------------------------------- Infos

async function Infos({ choisi }: { readonly choisi: string | undefined }) {
  const { t } = await langueEtTextes();
  const blocs = await blocsAdmin();

  const libelle = (cle: string): string => {
    if (cle === "loin.diffusion") return t.loin.diffusion_titre;
    return t.infos[cle.slice("infos.".length) as "venir"];
  };

  const bloc: BlocAdmin | undefined = blocs.find((candidat) => candidat.cle === choisi);

  if (bloc === undefined) {
    return (
      <Liste
        section="infos"
        libelleModifier={t.admin_contenus.modifier}
        elements={blocs.map((candidat) => {
          const attente = enAttente(candidat.texte_fr) || enAttente(candidat.texte_en);
          return {
            cle: candidat.cle,
            titre: libelle(candidat.cle),
            etat: attente ? t.admin_contenus.etat_a_completer : t.admin_contenus.etat_ecrit,
            attente,
          };
        })}
      />
    );
  }

  return (
    <section aria-labelledby="bloc" className="flex flex-col gap-5">
      <RetourListe section="infos" />
      <h2 id="bloc" className="jl-titre text-xl">
        {libelle(bloc.cle)}
      </h2>
      <form method="post" action="/admin/contenus/bloc" className="flex flex-col gap-5">
        <input type="hidden" name="cle" value={bloc.cle} />
        <Champ libelle={t.admin_contenus.texte_fr}>
          <textarea
            name="texte_fr"
            rows={5}
            required
            maxLength={2000}
            defaultValue={bloc.texte_fr}
            className={CHAMP}
            style={STYLE_CHAMP}
          />
        </Champ>
        <Champ libelle={t.admin_contenus.texte_en}>
          <textarea
            name="texte_en"
            rows={5}
            required
            maxLength={2000}
            defaultValue={bloc.texte_en}
            className={CHAMP}
            style={STYLE_CHAMP}
          />
        </Champ>
        {BLOCS_AVEC_LIEN.has(bloc.cle) ? (
          <Champ libelle={t.admin_contenus.lien} aide={t.admin_contenus.lien_aide}>
            <input
              type="url"
              name="lien"
              maxLength={500}
              defaultValue={bloc.lien_fr ?? ""}
              className={CHAMP}
              style={STYLE_CHAMP}
            />
          </Champ>
        ) : null}
        <button type="submit" className={`${BOUTON} self-start`} style={BORDURE}>
          {t.admin_contenus.enregistrer}
        </button>
      </form>
    </section>
  );
}

// ---------------------------------------------------------------------- FAQ

async function Faq({ choisi }: { readonly choisi: string | undefined }) {
  const { t } = await langueEtTextes();
  const questions = await faqAdmin();
  const nouvelle = choisi === "nouveau";
  const question: FaqAdmin | undefined = questions.find((candidat) => candidat.id === choisi);

  if (!nouvelle && question === undefined) {
    return (
      <Liste
        section="faq"
        libelleModifier={t.admin_contenus.modifier}
        ajout={{ cle: "nouveau", libelle: t.admin_contenus.ajouter_question }}
        elements={questions.map((candidat) => {
          const attente = enAttente(candidat.answer_fr) || enAttente(candidat.answer_en);
          return {
            cle: candidat.id,
            titre: candidat.question_fr,
            etat: !candidat.published
              ? t.admin_contenus.etat_masquee
              : attente
                ? t.admin_contenus.etat_a_completer
                : t.admin_contenus.etat_ecrit,
            attente,
          };
        })}
      />
    );
  }

  return (
    <section aria-labelledby="question" className="flex flex-col gap-5">
      <RetourListe section="faq" />
      <h2 id="question" className="jl-titre text-xl">
        {question?.question_fr ?? t.admin_contenus.ajouter_question}
      </h2>
      <form method="post" action="/admin/contenus/faq" className="flex flex-col gap-5">
        {question === undefined ? null : <input type="hidden" name="id" value={question.id} />}
        <input type="hidden" name="action" value={nouvelle ? "ajout" : "maj"} />
        <Champ libelle={t.admin_contenus.question_fr}>
          <input
            type="text"
            name="question_fr"
            required
            maxLength={300}
            defaultValue={question?.question_fr ?? ""}
            className={CHAMP}
            style={STYLE_CHAMP}
          />
        </Champ>
        <Champ libelle={t.admin_contenus.question_en}>
          <input
            type="text"
            name="question_en"
            required
            maxLength={300}
            defaultValue={question?.question_en ?? ""}
            className={CHAMP}
            style={STYLE_CHAMP}
          />
        </Champ>
        <Champ libelle={t.admin_contenus.reponse_fr}>
          <textarea
            name="answer_fr"
            rows={5}
            required
            maxLength={2000}
            defaultValue={question?.answer_fr ?? ""}
            className={CHAMP}
            style={STYLE_CHAMP}
          />
        </Champ>
        <Champ libelle={t.admin_contenus.reponse_en}>
          <textarea
            name="answer_en"
            rows={5}
            required
            maxLength={2000}
            defaultValue={question?.answer_en ?? ""}
            className={CHAMP}
            style={STYLE_CHAMP}
          />
        </Champ>
        <div className="flex flex-wrap items-end gap-6">
          <Champ libelle={t.admin_contenus.ordre}>
            <input
              type="number"
              name="sort_order"
              min={0}
              max={999}
              defaultValue={question?.sort_order ?? questions.length + 1}
              className={`${CHAMP} w-24 tabular-nums`}
              style={STYLE_CHAMP}
            />
          </Champ>
          <label className="jl-cible flex items-center gap-3">
            <input
              type="checkbox"
              name="published"
              value="1"
              defaultChecked={question?.published ?? true}
            />
            <span>{t.admin_contenus.publiee}</span>
          </label>
        </div>
        <div className="flex flex-wrap gap-4">
          <button type="submit" className={BOUTON} style={BORDURE}>
            {nouvelle ? t.admin_contenus.ajouter : t.admin_contenus.enregistrer}
          </button>
          {question === undefined ? null : (
            <button
              type="submit"
              name="supprimer"
              value="1"
              className={`${BOUTON} jl-doux`}
              style={BORDURE}
            >
              {t.admin_contenus.supprimer}
            </button>
          )}
        </div>
      </form>
    </section>
  );
}

// -------------------------------------------------------------- Hébergements

async function Hebergements({ choisi }: { readonly choisi: string | undefined }) {
  const { t } = await langueEtTextes();
  const liste = await hebergementsAdmin();
  const nouveau = choisi === "nouveau";
  const lit: HebergementAdmin | undefined = liste.find((candidat) => candidat.id === choisi);

  if (!nouveau && lit === undefined) {
    return (
      <div className="flex flex-col gap-6">
        {liste.length === 0 ? (
          <p className="jl-doux">{t.admin_contenus.aucun_hebergement}</p>
        ) : null}
        <Liste
          section="hebergements"
          libelleModifier={t.admin_contenus.modifier}
          ajout={{ cle: "nouveau", libelle: t.admin_contenus.ajouter_hebergement }}
          elements={liste.map((candidat) => ({
            cle: candidat.id,
            titre: candidat.name,
            etat:
              candidat.distance_km === null
                ? t.admin_contenus.etat_ecrit
                : `${candidat.distance_km} km`,
            attente: false,
          }))}
        />
      </div>
    );
  }

  return (
    <section aria-labelledby="hebergement" className="flex flex-col gap-5">
      <RetourListe section="hebergements" />
      <h2 id="hebergement" className="jl-titre text-xl">
        {lit?.name ?? t.admin_contenus.ajouter_hebergement}
      </h2>
      <form method="post" action="/admin/contenus/hebergement" className="flex flex-col gap-5">
        {lit === undefined ? null : <input type="hidden" name="id" value={lit.id} />}
        <input type="hidden" name="action" value={nouveau ? "ajout" : "maj"} />
        <Champ libelle={t.admin_contenus.nom}>
          <input
            type="text"
            name="name"
            required
            maxLength={200}
            defaultValue={lit?.name ?? ""}
            className={CHAMP}
            style={STYLE_CHAMP}
          />
        </Champ>
        <div className="flex flex-wrap gap-5">
          <Champ libelle={t.admin_contenus.distance}>
            <input
              type="text"
              inputMode="decimal"
              name="distance_km"
              maxLength={6}
              defaultValue={lit?.distance_km ?? ""}
              className={`${CHAMP} w-28 tabular-nums`}
              style={STYLE_CHAMP}
            />
          </Champ>
          <Champ libelle={t.admin_contenus.ordre}>
            <input
              type="number"
              name="sort_order"
              min={0}
              max={999}
              defaultValue={lit?.sort_order ?? liste.length + 1}
              className={`${CHAMP} w-24 tabular-nums`}
              style={STYLE_CHAMP}
            />
          </Champ>
        </div>
        <Champ libelle={t.admin_contenus.prix}>
          <input
            type="text"
            name="price_hint"
            maxLength={100}
            defaultValue={lit?.price_hint ?? ""}
            className={CHAMP}
            style={STYLE_CHAMP}
          />
        </Champ>
        <Champ libelle={t.admin_contenus.lien} aide={t.admin_contenus.lien_aide}>
          <input
            type="url"
            name="url"
            maxLength={500}
            defaultValue={lit?.url ?? ""}
            className={CHAMP}
            style={STYLE_CHAMP}
          />
        </Champ>
        <Champ libelle={t.admin_contenus.telephone}>
          <input
            type="tel"
            name="phone"
            maxLength={40}
            defaultValue={lit?.phone ?? ""}
            className={CHAMP}
            style={STYLE_CHAMP}
          />
        </Champ>
        <label className="jl-cible flex items-center gap-3">
          <input
            type="checkbox"
            name="shuttle"
            value="1"
            defaultChecked={lit?.shuttle === true}
          />
          <span>{t.admin_contenus.navette}</span>
        </label>
        <div className="flex flex-wrap gap-4">
          <button type="submit" className={BOUTON} style={BORDURE}>
            {nouveau ? t.admin_contenus.ajouter : t.admin_contenus.enregistrer}
          </button>
          {lit === undefined ? null : (
            <button
              type="submit"
              name="supprimer"
              value="1"
              className={`${BOUTON} jl-doux`}
              style={BORDURE}
            >
              {t.admin_contenus.supprimer}
            </button>
          )}
        </div>
      </form>
    </section>
  );
}
