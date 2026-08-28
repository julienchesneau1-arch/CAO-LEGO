"""L'atelier ouvert a des inconnus : la politique, et le trajet complet.

Ce qui est verifie ici n'est pas « le serveur repond » — c'est deja le sujet de
`test_bfk001_atelier.py` — mais les trois choses qu'heberger change et qu'un
usage local ne peut pas reveler : qui a le droit d'entrer, combien une seule
requete a le droit de couter, et le fait que deux visiteurs ne se marchent pas
dessus.
"""

from __future__ import annotations

import base64
import http.client
import json
import os
import subprocess
import sys
import threading
import time
import unittest

import bfk001 as bfk
from bfk001 import heberge
from bfk001.webapp import (DELAI_DE_SOCKET, Atelier, Resultats,
                           creer_serveur)

RACINE = os.path.dirname(os.path.abspath(__file__))
CLE = "cle-d-essai-assez-longue-pour-passer"


def photo(largeur=64, hauteur=64):
    pixels = bytearray()
    for y in range(hauteur):
        for x in range(largeur):
            pixels += bytes((30 + x * 200 // largeur, 90,
                             200 - y * 150 // hauteur))
    return bfk.write_png(bfk.Image(largeur, hauteur, bytes(pixels)))


class Horloge:
    """Un temps qu'on avance a la main : les expirations se testent en une
    milliseconde, pas en quatre heures."""

    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def avancer(self, secondes):
        self.t += secondes


# --------------------------------------------------------------------- #

class TestMemoireDuConteneur(unittest.TestCase):
    """`free` ment dans un conteneur. C'est le cgroup qui dit vrai."""

    def lecteur(self, table):
        def lire(chemin):
            if chemin not in table:
                raise OSError(chemin)
            return table[chemin]
        return lire

    def test_cgroup_v2_donne_la_limite(self):
        lire = self.lecteur({"/sys/fs/cgroup/memory.max": "536870912\n"})
        self.assertEqual(heberge.memoire_du_conteneur(lire), 536870912)

    def test_cgroup_v2_sans_limite_retombe_sur_meminfo(self):
        lire = self.lecteur({
            "/sys/fs/cgroup/memory.max": "max\n",
            "/proc/meminfo": "MemTotal:       16460492 kB\nMemFree: 1 kB\n",
        })
        self.assertEqual(heberge.memoire_du_conteneur(lire), 16460492 * 1024)

    def test_la_sentinelle_de_cgroup_v1_n_est_pas_lue_comme_une_limite(self):
        """Le piege : v1 ecrit un nombre astronomique pour dire « aucune
        limite ». Le lire tel quel ferait croire a un pentaoctet de memoire,
        donc a un plafond de tenons sans rapport avec la machine."""
        lire = self.lecteur({
            "/sys/fs/cgroup/memory/memory.limit_in_bytes":
                "9223372036854771712\n",
            "/proc/meminfo": "MemTotal:        1048576 kB\n",
        })
        self.assertEqual(heberge.memoire_du_conteneur(lire), 1048576 * 1024)

    def test_cgroup_v1_avec_une_vraie_limite(self):
        lire = self.lecteur({
            "/sys/fs/cgroup/memory/memory.limit_in_bytes": "268435456\n"})
        self.assertEqual(heberge.memoire_du_conteneur(lire), 268435456)

    def test_rien_de_lisible_ne_donne_pas_un_chiffre_invente(self):
        self.assertIsNone(heberge.memoire_du_conteneur(self.lecteur({})))


class TestPlafond(unittest.TestCase):
    """Deux bornes, et c'est la plus basse qui compte."""

    def test_petit_conteneur_c_est_la_memoire_qui_borne(self):
        memoire = 512 * 1024 * 1024
        self.assertLess(heberge.plafond_par_memoire(memoire),
                        heberge.plafond_par_duree())
        self.assertEqual(heberge.plafond_de_tenons(memoire),
                         heberge.plafond_par_memoire(memoire))

    def test_grand_conteneur_c_est_le_temps_de_reponse_qui_borne(self):
        memoire = 4096 * 1024 * 1024
        self.assertGreater(heberge.plafond_par_memoire(memoire),
                           heberge.plafond_par_duree())
        self.assertEqual(heberge.plafond_de_tenons(memoire),
                         heberge.plafond_par_duree())

    def test_deux_places_divisent_les_deux_plafonds(self):
        """Deux fabrications tiennent leur pointe EN MEME TEMPS, et — mesure —
        prennent chacune deux fois plus longtemps. Les deux bornes se divisent
        donc, pas seulement celle de la memoire."""
        memoire = 2048 * 1024 * 1024
        self.assertEqual(heberge.plafond_par_memoire(memoire, 2),
                         heberge.plafond_par_memoire(memoire, 1) // 2)
        self.assertEqual(heberge.plafond_par_duree(simultanees=2),
                         heberge.plafond_par_duree(simultanees=1) // 2)

    def test_un_conteneur_minuscule_donne_zero_et_non_un_nombre_negatif(self):
        self.assertEqual(heberge.plafond_par_memoire(16 * 1024 * 1024), 0)

    def test_zero_place_est_refuse(self):
        with self.assertRaises(ValueError):
            heberge.plafond_par_memoire(1 << 30, 0)
        with self.assertRaises(ValueError):
            heberge.plafond_par_duree(simultanees=0)

    def test_le_plafond_reste_loin_sous_celui_du_noyau(self):
        """Le plafond heberge doit etre plus bas que celui de la chaine, sinon
        il ne sert a rien. Mesure : 250 000 tenons ont demande 389 s et 3,4 Go
        — ce qu'aucune page web ni aucun petit conteneur ne tient."""
        from bfk001.pipeline import TENONS_MAXIMUM
        for mo in (512, 1024, 2048, 8192):
            self.assertLess(heberge.plafond_de_tenons(mo * 1024 * 1024),
                            TENONS_MAXIMUM)


class TestEtalonnage(unittest.TestCase):
    """La memoire est une propriete du logiciel ; la vitesse, non.

    Les memes mesures refaites sur une seconde machine du meme environnement
    ont rendu la colonne memoire a l'octet pres — 135 Mo, 217 Mo, identiques —
    et la colonne temps multipliee par 1,8. Un plafond de duree pose sur une
    constante y serait faux de 80 %.
    """

    def test_l_etalon_de_la_machine_de_mesure_redonne_la_constante(self):
        mesure = heberge.calibrer(lambda cote: heberge.CPU_ETALON_SECONDES)
        self.assertAlmostEqual(mesure, heberge.CPU_PAR_TENON, delta=0.1e-3)

    def test_une_machine_deux_fois_plus_lente_donne_un_cout_double(self):
        lent = heberge.calibrer(lambda cote: heberge.CPU_ETALON_SECONDES * 2)
        rapide = heberge.calibrer(lambda cote: heberge.CPU_ETALON_SECONDES)
        self.assertAlmostEqual(lent / rapide, 2.0, places=6)

    def test_l_etalon_fabrique_bien_une_mosaique_de_32_tenons_de_cote(self):
        vus = []
        heberge.calibrer(lambda cote: vus.append(cote) or 1.0)
        self.assertEqual(vus, [int(heberge.CPU_ETALON_TENONS ** 0.5)])

    def test_une_mesure_absurde_retombe_sur_la_constante(self):
        """Une horloge qui rend zero ne doit pas donner un plafond infini."""
        self.assertEqual(heberge.calibrer(lambda cote: 0.0),
                         heberge.CPU_PAR_TENON)

    def test_une_machine_plus_lente_abaisse_le_plafond_de_duree(self):
        rapide = heberge.plafond_par_duree(cpu_par_tenon=1.6e-3)
        lent = heberge.plafond_par_duree(cpu_par_tenon=3.2e-3)
        self.assertEqual(lent, rapide // 2)

    def test_un_cout_nul_est_refuse_plutot_que_de_donner_l_infini(self):
        with self.assertRaises(ValueError):
            heberge.plafond_par_duree(cpu_par_tenon=0.0)

    def test_la_memoire_ne_depend_PAS_de_la_vitesse(self):
        """Le pendant du test precedent : changer la vitesse ne doit rien
        changer au plafond memoire, sans quoi les deux bornes seraient
        confondues."""
        memoire = 512 * 1024 * 1024
        self.assertEqual(heberge.plafond_par_memoire(memoire),
                         heberge.plafond_par_memoire(memoire))
        self.assertEqual(
            heberge.plafond_de_tenons(memoire, cpu_par_tenon=1.0e-3),
            heberge.plafond_de_tenons(memoire, cpu_par_tenon=2.0e-3),
            "a 512 Mo c'est la memoire qui borne : la vitesse ne doit pas "
            "deplacer ce plafond-la")


class TestDebit(unittest.TestCase):

    def test_une_rafale_passe_puis_le_seau_est_vide(self):
        horloge = Horloge()
        debit = heberge.Debit(jetons=3, recharge=10.0, horloge=horloge)
        self.assertEqual([debit.prendre("a") for _ in range(3)],
                         [None, None, None])
        self.assertIsNotNone(debit.prendre("a"))

    def test_le_seau_se_recharge_avec_le_temps(self):
        horloge = Horloge()
        debit = heberge.Debit(jetons=2, recharge=10.0, horloge=horloge)
        debit.prendre("a"), debit.prendre("a")
        self.assertIsNotNone(debit.prendre("a"))
        horloge.avancer(10.0)
        self.assertIsNone(debit.prendre("a"))

    def test_deux_visiteurs_ont_deux_seaux(self):
        debit = heberge.Debit(jetons=1, recharge=10.0, horloge=Horloge())
        self.assertIsNone(debit.prendre("a"))
        self.assertIsNone(debit.prendre("b"))

    def test_le_dictionnaire_reste_borne_meme_quand_TOUT_est_refuse(self):
        """Le limiteur ne doit pas devenir l'attaque.

        La purge n'etait faite qu'au moment d'accorder un jeton. Un client qui
        change de cle a chaque requete etait donc toujours refuse — et faisait
        grossir le dictionnaire sans borne, c'est-a-dire exactement pendant une
        attaque, exactement quand il fallait qu'il tienne.
        """
        debit = heberge.Debit(jetons=1, recharge=1e9, cles_maximum=8,
                              horloge=Horloge())
        for tour in range(2):
            for i in range(200):
                debit.prendre(f"visiteur-{i}")
        self.assertLessEqual(len(debit._seaux), 8)

    def test_le_delai_rendu_est_celui_qu_il_faut_attendre(self):
        horloge = Horloge()
        debit = heberge.Debit(jetons=1, recharge=60.0, horloge=horloge)
        debit.prendre("a")
        attente = debit.prendre("a")
        self.assertAlmostEqual(attente, 60.0, places=3)
        horloge.avancer(30.0)
        self.assertAlmostEqual(debit.prendre("a"), 30.0, places=3)


class TestAdresseDuVisiteur(unittest.TestCase):
    """`X-Forwarded-For` est ecrit par le client autant que par les relais."""

    def test_sans_relais_declare_l_entete_n_est_pas_cru(self):
        adresse = heberge.adresse_du_visiteur(
            {"X-Forwarded-For": "1.2.3.4"}, "10.0.0.9")
        self.assertEqual(adresse, "10.0.0.9")

    def test_avec_un_relais_le_dernier_maillon_fait_foi(self):
        adresse = heberge.adresse_du_visiteur(
            {"X-Forwarded-For": "203.0.113.7"}, "10.0.0.9", relais=1)
        self.assertEqual(adresse, "203.0.113.7")

    def test_un_prefixe_fabrique_par_le_client_ne_change_rien(self):
        """C'est tout l'interet de compter les relais : le client peut ecrire
        ce qu'il veut AVANT ce que le relais ajoute, jamais apres."""
        adresse = heberge.adresse_du_visiteur(
            {"X-Forwarded-For": "9.9.9.9, 8.8.8.8, 203.0.113.7"},
            "10.0.0.9", relais=1)
        self.assertEqual(adresse, "203.0.113.7")

    def test_moins_de_maillons_qu_annonce_retombe_sur_le_pair(self):
        adresse = heberge.adresse_du_visiteur({}, "10.0.0.9", relais=2)
        self.assertEqual(adresse, "10.0.0.9")


class TestHebergement(unittest.TestCase):

    def creer(self, **kwargs):
        kwargs.setdefault("cle", CLE)
        kwargs.setdefault("fabrique_atelier", lambda: object())
        kwargs.setdefault("plafond_tenons", 20_000)
        return heberge.Hebergement(**kwargs)

    def visite(self, chemin="/", requete="", entetes=None, pair="10.0.0.1"):
        return heberge.Visite(chemin=chemin, methode="GET", pair=pair,
                              entetes=entetes or {}, requete=requete)

    def test_une_cle_courte_est_refusee_au_demarrage(self):
        with self.assertRaises(ValueError):
            self.creer(cle="court")

    def test_un_plafond_sous_le_plancher_est_refuse_au_demarrage(self):
        """Servir une application qui refuse tout ce qu'on lui demande est pire
        que ne pas la servir : l'erreur doit tomber au demarrage."""
        with self.assertRaises(ValueError):
            self.creer(plafond_tenons=heberge.TENONS_PLANCHER - 1)

    def test_sans_cle_la_page_est_refusee_en_html_lisible(self):
        accueil = self.creer().accueillir(self.visite("/"))
        self.assertTrue(accueil.termine)
        self.assertEqual(accueil.code, 401)
        self.assertIn("atelier prive", accueil.corps_html.lower())

    def test_un_appel_de_la_page_est_refuse_en_json_et_non_en_html(self):
        """Un `fetch` qui recoit du HTML leve sur l'analyse JSON, et le visiteur
        lit « SyntaxError » la ou il fallait lire « session expiree »."""
        accueil = self.creer().accueillir(self.visite("/fabriquer"))
        self.assertEqual(accueil.code, 401)
        self.assertIsNone(accueil.corps_html)
        self.assertIn("session", accueil.message)

    def test_la_page_de_refus_ne_recopie_rien_du_client(self):
        """Elle a un instant recopie l'en-tete `Host`. Une page qui reflete ce
        que le client envoie offre au premier venu d'ecrire ce que lira le
        visiteur suivant."""
        self.assertNotIn("%s", heberge.PAGE_CLE)
        self.assertNotIn("{}", heberge.PAGE_CLE)

    def test_la_bonne_cle_ouvre_une_session_et_pose_un_temoin(self):
        accueil = self.creer().accueillir(self.visite("/", requete="cle=" + CLE))
        self.assertEqual(accueil.code, 303)
        entetes = dict(accueil.entetes)
        self.assertEqual(entetes["Location"], "/")
        temoin = entetes["Set-Cookie"]
        self.assertIn("HttpOnly", temoin)
        self.assertIn("Secure", temoin)
        self.assertIn("SameSite=Lax", temoin)

    def test_la_cle_ne_reste_pas_dans_la_barre_d_adresse(self):
        """303 et non 200 : sans redirection, la cle serait dans l'historique
        et dans le prochain lien copie-colle."""
        accueil = self.creer().accueillir(self.visite("/", requete="cle=" + CLE))
        self.assertEqual(accueil.code, 303)

    def test_une_mauvaise_cle_ne_pose_aucun_temoin(self):
        accueil = self.creer().accueillir(self.visite("/", requete="cle=faux"))
        self.assertEqual(accueil.code, 401)
        self.assertNotIn("Set-Cookie", dict(accueil.entetes))

    def test_les_essais_de_cle_sont_freines_a_part(self):
        """Le debit des fabrications se recharge en secondes : il laisserait
        essayer des milliers de cles par jour."""
        hebergement = self.creer()
        codes = [hebergement.accueillir(
            self.visite("/", requete="cle=faux")).code for _ in range(20)]
        self.assertIn(429, codes)

    def test_le_temoin_rend_le_meme_atelier_deux_fois(self):
        compteur = [0]
        def fabrique():
            compteur[0] += 1
            return f"atelier-{compteur[0]}"
        hebergement = self.creer(fabrique_atelier=fabrique)
        temoin = dict(hebergement.accueillir(
            self.visite("/", requete="cle=" + CLE)).entetes)["Set-Cookie"]
        jeton = temoin.split(";")[0]
        a = hebergement.accueillir(self.visite("/", entetes={"Cookie": jeton}))
        b = hebergement.accueillir(self.visite("/", entetes={"Cookie": jeton}))
        self.assertEqual(a.atelier, b.atelier)
        self.assertEqual(compteur[0], 1)

    def test_deux_visiteurs_ont_deux_ateliers(self):
        compteur = [0]
        def fabrique():
            compteur[0] += 1
            return f"atelier-{compteur[0]}"
        hebergement = self.creer(fabrique_atelier=fabrique)
        jetons = []
        for _ in range(2):
            temoin = dict(hebergement.accueillir(
                self.visite("/", requete="cle=" + CLE)).entetes)["Set-Cookie"]
            jetons.append(temoin.split(";")[0])
        ateliers = [hebergement.accueillir(
            self.visite("/", entetes={"Cookie": j})).atelier for j in jetons]
        self.assertNotEqual(ateliers[0], ateliers[1])

    def test_un_temoin_invente_ne_donne_pas_d_atelier(self):
        hebergement = self.creer()
        accueil = hebergement.accueillir(
            self.visite("/", entetes={"Cookie": "bfk_session=invente"}))
        self.assertEqual(accueil.code, 401)

    def test_un_entete_cookie_abime_ne_leve_pas(self):
        hebergement = self.creer()
        for brut in ("", ";;;", "=", "bfk_session", "autre=1; bfk_session="):
            accueil = hebergement.accueillir(
                self.visite("/", entetes={"Cookie": brut}))
            self.assertEqual(accueil.code, 401, brut)

    def test_une_session_inactive_est_oubliee(self):
        horloge = Horloge()
        hebergement = self.creer(horloge=horloge)
        temoin = dict(hebergement.accueillir(
            self.visite("/", requete="cle=" + CLE)).entetes)["Set-Cookie"]
        jeton = temoin.split(";")[0]
        self.assertIsNotNone(hebergement.accueillir(
            self.visite("/", entetes={"Cookie": jeton})).atelier)
        horloge.avancer(heberge.DUREE_DE_SESSION + 1)
        self.assertEqual(hebergement.accueillir(
            self.visite("/", entetes={"Cookie": jeton})).code, 401)

    def test_le_nombre_de_sessions_est_borne(self):
        hebergement = self.creer()
        for _ in range(heberge.SESSIONS_MAXIMUM + 20):
            hebergement.ouvrir_session()
        self.assertLessEqual(len(hebergement._sessions),
                             heberge.SESSIONS_MAXIMUM)

    def test_le_chantier_n_a_qu_une_place_et_la_rend(self):
        hebergement = self.creer(simultanees=1)
        with hebergement.chantier():
            with self.assertRaises(heberge.Occupe):
                with hebergement.chantier():
                    pass
        with hebergement.chantier():      # la place a bien ete rendue
            pass

    def test_une_erreur_pendant_la_fabrication_rend_la_place(self):
        hebergement = self.creer(simultanees=1)
        with self.assertRaises(ZeroDivisionError):
            with hebergement.chantier():
                1 / 0
        with hebergement.chantier():
            pass

    def test_une_place_refusee_n_est_pas_rendue_en_trop(self):
        """`BoundedSemaphore` leverait si un refus relachait quand meme : le
        test existe pour que ce soit ce fichier qui le dise, pas la production.
        """
        hebergement = self.creer(simultanees=1)
        with hebergement.chantier():
            for _ in range(3):
                with self.assertRaises(heberge.Occupe):
                    with hebergement.chantier():
                        pass
        with hebergement.chantier():
            pass


class TestMagasinDeResultats(unittest.TestCase):
    """Compter les resultats ne borne rien : c'est le poids qui compte."""

    def test_le_poids_total_est_borne(self):
        magasin = Resultats(gardes=100, octets=1000)
        for _ in range(10):
            magasin.poser({"a.bin": b"x" * 400})
        self.assertLessEqual(len(magasin), 3)

    def test_le_nombre_est_borne_aussi(self):
        magasin = Resultats(gardes=2, octets=1 << 30)
        for _ in range(5):
            magasin.poser({"a.bin": b"x"})
        self.assertEqual(len(magasin), 2)

    def test_un_seul_resultat_plus_gros_que_la_borne_reste_lisible(self):
        """Sinon la mosaique qu'on vient de fabriquer serait oubliee avant
        d'avoir pu etre telechargee : le refus doit venir du plafond de tenons,
        pas d'un magasin qui se vide tout seul."""
        magasin = Resultats(gardes=8, octets=10)
        jeton = magasin.poser({"a.bin": b"x" * 5000})
        self.assertEqual(len(magasin.un(jeton, "a.bin")), 5000)

    def test_un_jeton_oublie_leve_KeyError(self):
        magasin = Resultats(gardes=1, octets=1 << 30)
        vieux = magasin.poser({"a.bin": b"x"})
        magasin.poser({"b.bin": b"y"})
        with self.assertRaises(KeyError):
            magasin.tous(vieux)

    def test_les_jetons_ne_se_devinent_pas(self):
        magasin = Resultats()
        jetons = {magasin.poser({"a": b"x"}) for _ in range(50)}
        self.assertEqual(len(jetons), 50)
        self.assertTrue(all(len(j) >= 20 for j in jetons))

    def test_deux_ateliers_peuvent_partager_un_magasin(self):
        """C'est ce qui rend la borne vraie quand chaque visiteur a son
        atelier : un magasin par visiteur multiplierait la borne par le nombre
        de visiteurs, donc ne bornerait plus rien."""
        magasin = Resultats()
        a = Atelier(palette=PALETTE, palette_complete=PALETTE,
                    resultats=magasin)
        b = Atelier(palette=PALETTE, palette_complete=PALETTE,
                    resultats=magasin)
        self.assertIs(a.resultats, b.resultats)


class TestPlafondDansLAtelier(unittest.TestCase):

    def atelier(self, plafond):
        return Atelier(palette=PALETTE, palette_complete=PALETTE,
                       plafond_tenons=plafond)

    def test_en_local_il_n_y_a_pas_de_plafond_supplementaire(self):
        self.assertIsNone(Atelier(palette=PALETTE,
                                  palette_complete=PALETTE).plafond_tenons)

    def test_au_dela_du_plafond_le_refus_dit_le_chiffre_et_la_raison(self):
        atelier = self.atelier(1024)
        with self.assertRaises(ValueError) as leve:
            atelier.fabriquer({"photo": base64.b64encode(photo()).decode(),
                               "reglages": {"studs": 64, "hauteur": 64}})
        message = str(leve.exception)
        self.assertIn("4096", message)
        self.assertIn("1024", message)
        self.assertIn("32 x 32", message)

    def test_la_hauteur_est_celle_de_la_PHOTO_et_non_le_carre(self):
        """Un portrait demande a 48 tenons de large en fait 64 de haut. Verifier
        48 x 48 laisserait passer un tiers de surface de plus que le plafond.
        """
        portrait = base64.b64encode(photo(48, 64)).decode()
        atelier = self.atelier(2000)          # 48 x 48 = 2304 > 2000 aussi
        with self.assertRaises(ValueError) as leve:
            atelier.fabriquer({"photo": portrait, "reglages": {"studs": 48}})
        self.assertIn("48 x 64", str(leve.exception))

    def test_sous_le_plafond_la_fabrication_a_lieu(self):
        atelier = self.atelier(heberge.TENONS_PLANCHER)
        reponse = atelier.fabriquer(
            {"photo": base64.b64encode(photo()).decode(),
             "reglages": {"studs": 16, "hauteur": 16, "titre": "essai"}})
        self.assertIn("jeton", reponse)

    def test_le_conseil_est_borne_lui_aussi(self):
        """Il met QUATRE formats en balance : il coute plus cher qu'une
        fabrication de la meme taille, pas moins."""
        atelier = self.atelier(1024)
        with self.assertRaises(ValueError):
            atelier.conseiller({"photo": base64.b64encode(photo()).decode(),
                                "reglages": {"studs": 64, "hauteur": 64}})

    def test_la_page_recoit_le_plafond(self):
        self.assertEqual(self.atelier(4096).etat_catalogues()["plafond"], 4096)
        self.assertIsNone(Atelier(palette=PALETTE, palette_complete=PALETTE)
                          .etat_catalogues()["plafond"])


# --------------------------------------------------------------------- #
# Le trajet complet, en vrai HTTP
# --------------------------------------------------------------------- #

class _ServeurHeberge:
    """Un serveur heberge sur un port libre, pour la duree d'une classe."""

    @classmethod
    def demarrer(cls, plafond=heberge.TENONS_PLANCHER * 4, simultanees=1,
                 debit=None):
        magasin = Resultats()
        def fabrique():
            return Atelier(palette=PALETTE, palette_complete=PALETTE,
                           dossier=None, memoire=False,
                           plafond_tenons=plafond, resultats=magasin)
        hebergement = heberge.Hebergement(
            cle=CLE, fabrique_atelier=fabrique, plafond_tenons=plafond,
            simultanees=simultanees, securise=False,
            debit=debit or heberge.Debit(jetons=1000, recharge=1.0))
        serveur = creer_serveur("127.0.0.1", 0, fabrique(), hebergement)
        fil = threading.Thread(target=serveur.serve_forever, daemon=True)
        fil.start()
        return serveur, hebergement


class TestTrajetHeberge(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.serveur, cls.hebergement = _ServeurHeberge.demarrer()
        cls.port = cls.serveur.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        cls.serveur.server_close()

    def appel(self, methode, chemin, corps=None, temoin=None):
        lien = http.client.HTTPConnection("127.0.0.1", self.port, timeout=180)
        entetes, charge = {}, None
        if corps is not None:
            charge = json.dumps(corps).encode("utf-8")
            entetes["Content-Type"] = "application/json"
        if temoin:
            entetes["Cookie"] = temoin
        lien.request(methode, chemin, charge, entetes)
        reponse = lien.getresponse()
        donnees = reponse.read()
        tete = dict(reponse.getheaders())
        code = reponse.status
        lien.close()
        return code, tete, donnees

    def entrer(self):
        _, tete, _ = self.appel("GET", "/?cle=" + CLE)
        return tete["Set-Cookie"].split(";")[0]

    def test_la_page_ne_se_sert_pas_sans_la_cle(self):
        code, tete, corps = self.appel("GET", "/")
        self.assertEqual(code, 401)
        self.assertTrue(tete["Content-Type"].startswith("text/html"))
        self.assertIn(b"prive", corps)

    def test_le_lien_a_la_cle_ouvre_la_session_puis_la_page(self):
        code, tete, _ = self.appel("GET", "/?cle=" + CLE)
        self.assertEqual(code, 303)
        temoin = tete["Set-Cookie"].split(";")[0]
        code, _, corps = self.appel("GET", "/", temoin=temoin)
        self.assertEqual(code, 200)
        self.assertIn(b"<!doctype", corps.lower()[:200])

    def test_une_fabrication_complete_et_son_telechargement(self):
        temoin = self.entrer()
        code, _, corps = self.appel(
            "POST", "/fabriquer",
            {"photo": base64.b64encode(photo()).decode(),
             "reglages": {"studs": 16, "hauteur": 16, "titre": "essai"}},
            temoin=temoin)
        self.assertEqual(code, 200, corps[:200])
        reponse = json.loads(corps)
        notice = [n for n in reponse["fichiers"] if n.endswith(".pdf")][0]
        code, _, contenu = self.appel(
            "GET", f"/fichier/{reponse['jeton']}/{notice}", temoin=temoin)
        self.assertEqual(code, 200)
        self.assertTrue(contenu.startswith(b"%PDF"))
        code, _, archive = self.appel(
            "GET", f"/telecharger/{reponse['jeton']}.zip", temoin=temoin)
        self.assertEqual(code, 200)
        self.assertEqual(archive[:2], b"PK")

    def test_au_dela_du_plafond_le_refus_est_explique_et_non_une_panne(self):
        temoin = self.entrer()
        code, _, corps = self.appel(
            "POST", "/fabriquer",
            {"photo": base64.b64encode(photo()).decode(),
             "reglages": {"studs": 400, "hauteur": 400}}, temoin=temoin)
        self.assertEqual(code, 400)
        self.assertIn("tenons", json.loads(corps)["erreur"])

    def test_la_palette_ne_se_change_pas_depuis_la_page(self):
        """Hebergee, cette route ferait sortir une requete de la machine de qui
        heberge, a la demande d'un visiteur, et changerait la palette de tout
        le monde."""
        temoin = self.entrer()
        code, _, _ = self.appel("POST", "/palette", {}, temoin=temoin)
        self.assertEqual(code, 403)

    def test_le_catalogue_d_un_visiteur_ne_touche_pas_celui_de_l_autre(self):
        """C'est la difference entre « une installation » et « un service ».
        Un catalogue partiel depose par l'un degraderait la liste de course de
        l'autre sans que personne comprenne pourquoi."""
        un, deux = self.entrer(), self.entrer()
        catalogue = base64.b64encode(
            b"element_id,design_id,lego_color_id\n"
            b"4211063,3070,26\n4211064,3024,21\n").decode()
        code, _, corps = self.appel("POST", "/catalogues",
                                    {"elements": catalogue}, temoin=deux)
        self.assertEqual(code, 200, corps[:200])
        _, _, etat_un = self.appel("GET", "/catalogues", temoin=un)
        _, _, etat_deux = self.appel("GET", "/catalogues", temoin=deux)
        self.assertIsNone(json.loads(etat_un)["elements"])
        self.assertEqual(json.loads(etat_deux)["elements"]["references"], 2)

    def test_un_temoin_invente_n_ouvre_rien(self):
        code, _, corps = self.appel(
            "POST", "/fabriquer", {"photo": ""},
            temoin="bfk_session=jeton-invente-par-le-client")
        self.assertEqual(code, 401)
        self.assertIn("erreur", json.loads(corps))


class TestUneSeuleFabricationALaFois(unittest.TestCase):
    """La mesure dit que deux fabrications en parallele ne servent personne :
    chacune prend deux fois plus longtemps et le debit total baisse. Le second
    visiteur doit donc etre refuse TOUT DE SUITE, et non attendre en silence.
    """

    def test_le_second_est_refuse_sans_attendre(self):
        serveur, hebergement = _ServeurHeberge.demarrer()
        port = serveur.server_address[1]
        try:
            def temoin_neuf():
                lien = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
                lien.request("GET", "/?cle=" + CLE)
                reponse = lien.getresponse()
                reponse.read()
                jeton = dict(reponse.getheaders())["Set-Cookie"].split(";")[0]
                lien.close()
                return jeton

            resultats = [None, None]

            def fabriquer(temoin, indice):
                lien = http.client.HTTPConnection("127.0.0.1", port, timeout=180)
                depart = time.monotonic()
                lien.request(
                    "POST", "/fabriquer",
                    json.dumps({"photo": base64.b64encode(photo(128, 128)).decode(),
                                "reglages": {"studs": 40, "hauteur": 40}}
                               ).encode("utf-8"),
                    {"Content-Type": "application/json", "Cookie": temoin})
                reponse = lien.getresponse()
                reponse.read()
                resultats[indice] = (reponse.status, time.monotonic() - depart,
                                     dict(reponse.getheaders()).get("Retry-After"))
                lien.close()

            un, deux = temoin_neuf(), temoin_neuf()
            fils = [threading.Thread(target=fabriquer, args=(un, 0)),
                    threading.Thread(target=fabriquer, args=(deux, 1))]
            fils[0].start()
            # Attendre que la place SOIT PRISE, et non un delai suppose plus
            # court que la fabrication : un test de concurrence qui repose sur
            # un `sleep` mesure la vitesse de la machine, pas la politique.
            limite = time.monotonic() + 60.0
            while (hebergement._places._value != 0
                   and time.monotonic() < limite):
                time.sleep(0.01)
            self.assertEqual(hebergement._places._value, 0,
                             "la premiere fabrication n'a jamais commence")
            fils[1].start()
            for fil in fils:
                fil.join(timeout=200)

            codes = sorted(code for code, _, _ in resultats)
            self.assertEqual(codes, [200, 503], resultats)
            refuse = [(duree, retard) for code, duree, retard in resultats
                      if code == 503][0]
            self.assertLess(refuse[0], 3.0, "le refus doit etre immediat")
            self.assertIsNotNone(refuse[1], "il doit dire quand revenir")
        finally:
            serveur.shutdown()
            serveur.server_close()


class TestLeDebitFreineUnVisiteurTropRapide(unittest.TestCase):

    def test_apres_la_rafale_le_visiteur_est_freine_et_on_lui_dit_quand(self):
        serveur, _ = _ServeurHeberge.demarrer(
            debit=heberge.Debit(jetons=2, recharge=60.0))
        port = serveur.server_address[1]
        try:
            lien = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
            lien.request("GET", "/?cle=" + CLE)
            reponse = lien.getresponse()
            reponse.read()
            temoin = dict(reponse.getheaders())["Set-Cookie"].split(";")[0]
            lien.close()

            codes, retard = [], None
            for _ in range(4):
                lien = http.client.HTTPConnection("127.0.0.1", port, timeout=180)
                lien.request(
                    "POST", "/fabriquer",
                    json.dumps({"photo": base64.b64encode(photo()).decode(),
                                "reglages": {"studs": 12, "hauteur": 12}}
                               ).encode("utf-8"),
                    {"Content-Type": "application/json", "Cookie": temoin})
                reponse = lien.getresponse()
                reponse.read()
                codes.append(reponse.status)
                if reponse.status == 429:
                    retard = dict(reponse.getheaders()).get("Retry-After")
                lien.close()
            self.assertIn(429, codes)
            self.assertIsNotNone(retard)
        finally:
            serveur.shutdown()
            serveur.server_close()


class TestLeServeurLocalNEstPasChange(unittest.TestCase):
    """La politique n'existe qu'avec elle. Sans `hebergement`, le trajet local
    doit etre exactement celui d'avant qu'elle existe."""

    def test_sans_hebergement_aucun_delai_n_est_pose_sur_les_connexions(self):
        serveur = creer_serveur("127.0.0.1", 0,
                                Atelier(palette=PALETTE,
                                        palette_complete=PALETTE))
        try:
            self.assertIsNone(serveur.RequestHandlerClass.timeout)
            self.assertIsNone(serveur.RequestHandlerClass.hebergement)
        finally:
            serveur.server_close()

    def test_avec_hebergement_un_delai_est_pose(self):
        """Sans delai, un client qui annonce un corps et n'en envoie jamais la
        fin garde un fil pour lui, indefiniment et gratuitement."""
        serveur, _ = _ServeurHeberge.demarrer()
        try:
            self.assertEqual(serveur.RequestHandlerClass.timeout,
                             DELAI_DE_SOCKET)
        finally:
            serveur.shutdown()
            serveur.server_close()


class TestLeLanceurHeberge(unittest.TestCase):

    def lancer(self, **variables):
        env = dict(os.environ, **variables)
        env.pop("BFK_CLE", None)
        env.update({k: v for k, v in variables.items()})
        return subprocess.run([sys.executable, "heberger_lego_art.py"],
                              cwd=RACINE, env=env, capture_output=True,
                              text=True, timeout=120)

    def test_sans_cle_il_ne_demarre_pas_et_en_propose_une(self):
        sortie = self.lancer()
        self.assertEqual(sortie.returncode, 2)
        self.assertIn("BFK_CLE=", sortie.stderr)

    def test_une_cle_trop_courte_est_refusee_comme_une_absence(self):
        sortie = self.lancer(BFK_CLE="court")
        self.assertEqual(sortie.returncode, 2)

    def test_un_conteneur_trop_petit_le_dit_au_lieu_de_servir_un_atelier_inutile(self):
        sortie = self.lancer(BFK_CLE=CLE, BFK_MEMOIRE_MO="96")
        self.assertEqual(sortie.returncode, 2)
        self.assertIn("plancher", sortie.stderr)


PALETTE = None


def setUpModule():
    global PALETTE
    from bfk001.pipeline import palette_utilisable
    complete, note = palette_utilisable()
    PALETTE = complete if note[0] == "alerte" else complete.solids_only()


if __name__ == "__main__":
    unittest.main()
