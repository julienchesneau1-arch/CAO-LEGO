import { Monogram } from "./Monogram";
import { PileCouleurs } from "./PileCouleurs";

type Props = {
  readonly hauteurMonogramme?: number;
  readonly mention: string;
  readonly titreAccessible?: string;
};

/** Monogramme + mention « DEPUIS 2018 » + pile des cinq couleurs (brief §3). */
export function Signature({
  hauteurMonogramme = 72,
  mention,
  titreAccessible,
}: Props) {
  return (
    <div className="flex items-center gap-6">
      <PileCouleurs />
      <div className="flex flex-col items-start gap-3">
        <Monogram hauteur={hauteurMonogramme} {...(titreAccessible ? { titre: titreAccessible } : {})} />
        <span className="jl-etiquette">{mention}</span>
      </div>
    </div>
  );
}
