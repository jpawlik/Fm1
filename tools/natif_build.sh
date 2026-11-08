#!/usr/bin/env bash
# Compile un firmware depuis ses sources pour le navigateur, avec le script de son auteur, puis prépare
# natif/<id>/ pour le panneau. Lancé par l'action GitHub, un firmware par tâche.
#   tools/natif_build.sh <id> <dossier du dépôt du firmware> <script de compilation> <dossier de sortie>
# Sortie : <sortie>/<id>/{<nom>.wasm, worklet.js, LICENSE.txt, natif.json}, ou rien si la compilation échoue
# ou si le worklet ne parle pas un des protocoles connus (Felucca, X0X, ChoralRoot, sim, MEL).
# Facultatifs, depuis tools/natif.json : NATIF_AVANT, une commande lancée à la racine du dépôt avant le script ;
# NATIF_WASM, le .wasm à retenir quand le script en produit plusieurs ; NATIF_OUTILS (relatifs à NATIF_OUTILS_BASE),
# des modules de la page du firmware joints sous outils/, dont NATIF_ECHANTILLONS, sa préparation des échantillons ;
# NATIF_WORKLET (relatif à ce dépôt) et NATIF_DIALECTE, notre worklet pour un firmware dont la page n'en a pas ;
# NATIF_CONSTRUCTION, une commande lancée à la place du script (elle trouve ce dépôt dans $HERE).
set -uo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)     # ce dépôt : ses worklets (tools/worklets/) pour les firmwares qui n'en ont pas
ID=$1 REPO=$(cd "$2" && pwd) SCRIPT=$3 OUT=$4
mkdir -p "$OUT"; OUT=$(cd "$OUT" && pwd)
cd "$REPO"
touch /tmp/natif-start; sleep 1
LOG=/tmp/natif-$ID.log; : > "$LOG"
# un firmware écarté : la raison et la fin du journal, en annotation de l'action (lisible sans les journaux)
echec() {
  echo "natif $ID : $1"
  printf '::warning title=natif %s::%s\n' "$ID" "$( { echo "$1"; tail -n 25 "$LOG"; } | sed 's/%/%25/g' | tr -d '\r' | sed ':a;N;$!ba;s/\n/%0A/g')"
  exit 0
}
command -v zig >/dev/null 2>&1 && export ZIG="${ZIG:-$(command -v zig)}"   # les scripts qui compilent avec zig cc
# wasm-ld et wasm-opt d'Emscripten, en fin de PATH : pour les scripts qui lient avec clang ou passent par Asyncify
E=$(command -v emcc 2>/dev/null) && [ -x "$(dirname "$E")/../bin/wasm-ld" ] && PATH="$PATH:$(cd "$(dirname "$E")/../bin" && pwd)"

# en-têtes générés, pour les firmwares de la famille Felucca qui les demandent (polices, tables, échantillons) :
# tools/build.py du projet où vit le script (le dépôt, ou un sous-dossier comme firmware/ ou felucca-base/)
P=$(dirname "$SCRIPT")
while :; do
  if [ -f "$P/tools/build.py" ] && grep -q "def generate" "$P/tools/build.py"; then
    (cd "$P" && python3 -c "import importlib.util as u; s=u.spec_from_file_location('b','tools/build.py'); b=u.module_from_spec(s); s.loader.exec_module(b); b.generate()") >>"$LOG" 2>&1 \
      || echo "natif $ID : génération des en-têtes en échec (on continue)"
    break
  fi
  [ "$P" = . ] && break; P=$(dirname "$P")
done

export HERE                                # (NATIF_AVANT et NATIF_CONSTRUCTION y trouvent nos scripts)
if [ -n "${NATIF_AVANT:-}" ]; then bash -c "$NATIF_AVANT" >>"$LOG" 2>&1 || echo "natif $ID : préparation en échec (on continue)"; fi
if [ -n "${NATIF_CONSTRUCTION:-}" ]; then bash -c "$NATIF_CONSTRUCTION" 2>&1 | tee -a "$LOG"
else EMU_PREVIEW=0 bash "$SCRIPT" 2>&1 | tee -a "$LOG"; fi; [ "${PIPESTATUS[0]}" = 0 ] || echec "la compilation a échoué"

CANDIDATS=$(find . -name node_modules -prune -o -name '*.wasm' -newer /tmp/natif-start -print)
[ -n "$CANDIDATS" ] || echec "aucun .wasm produit"
WASM="" WORKLET=""
[ -n "${NATIF_WASM:-}" ] && CANDIDATS=./$NATIF_WASM
for w in $CANDIDATS; do                    # de préférence le .wasm qui a son worklet à côté
  k=$(ls "$(dirname "$w")"/worklet*.js 2>/dev/null | head -1)
  if [ -n "$k" ]; then WASM=$w WORKLET=$k; break; fi
done
if [ -z "$WASM" ]; then WASM=$(echo "$CANDIDATS" | head -1); WORKLET=$(ls "$(dirname "$SCRIPT")"/worklet*.js 2>/dev/null | head -1); fi
[ -n "${NATIF_WORKLET:-}" ] && WORKLET="$HERE/$NATIF_WORKLET"
echo "natif $ID : .wasm produits : $(echo $CANDIDATS)"
[ -n "$WORKLET" ] || echec "pas de worklet à côté du .wasm"

if [ -n "${NATIF_DIALECTE:-}" ]; then DIALECT=$NATIF_DIALECTE
elif grep -q 'msg.leds' "$WORKLET" && grep -q 'type === "buttons"' "$WORKLET"; then DIALECT=felucca
elif grep -q 'web_lit_buttons() >>> 0, keys' "$WORKLET" && grep -q 'web_key(m.key' "$WORKLET" && ! grep -q 'type === "keys"' "$WORKLET"; then DIALECT=monk   # X0X, touche par touche
elif grep -q 'web_lit_buttons() >>> 0, keys' "$WORKLET" && grep -q 'type === "buttons"' "$WORKLET"; then DIALECT=x0x
elif grep -q 'web_flash_stage' "$WORKLET" && grep -q 'case "buttons"' "$WORKLET"; then DIALECT=choralroot
elif grep -q 'sim_leds_buttons' "$WORKLET" && grep -q 'processorOptions' "$WORKLET"; then DIALECT=sim
elif grep -q 'web_settings_set_len' "$WORKLET" && grep -q 'web_button(' "$WORKLET"; then DIALECT=mel
elif grep -q 't === "wasm"' "$WORKLET" && grep -q 'w_frame(' "$WORKLET"; then DIALECT=m2k
else echec "protocole du worklet inconnu ($(basename "$WORKLET"))"; fi

D="$OUT/$ID"; mkdir -p "$D"
cp "$WASM" "$D/"
cp "$WORKLET" "$D/worklet.js"
# LOOM uses an upstream fm1-base worklet with no app-specific callbacks.
# Avoid inheriting callbacks left by another firmware in the AudioWorkletGlobalScope.
if [ "$ID" = "loom" ]; then
  sed -i '1i globalThis.fm1App = {};' "$D/worklet.js"
fi
# les modules que le worklet importe à côté de lui (import … from "./x.js"), sur deux niveaux
for f in "$WORKLET" $(grep -oE "from \"\./[^\"]+\.js\"" "$WORKLET" | sed -E 's/from "\.\/(.*)"/\1/' | sed "s#^#$(dirname "$WORKLET")/#"); do
  for m in $(grep -oE "from \"\./[^\"]+\.js\"" "$f" | sed -E 's/from "\.\/(.*)"/\1/'); do
    cp "$(dirname "$WORKLET")/$m" "$D/$m" || echo "natif $ID : module $m introuvable"
  done
done
if [ -n "${NATIF_OUTILS:-}" ]; then
  for f in $NATIF_OUTILS; do
    mkdir -p "$D/outils/$(dirname "$f")"
    cp "${NATIF_OUTILS_BASE:-.}/$f" "$D/outils/$f" || { rm -rf "$D"; echec "outil $f introuvable"; }
  done
fi
LIC=$(ls LICENSE LICENSE.* COPYING 2>/dev/null | head -1); [ -n "$LIC" ] && cp "$LIC" "$D/LICENSE.txt"
# deux modifications, seulement : un nom de processeur propre à ce firmware (plusieurs dans la même page),
# et l'écran publié 60 fois par seconde au lieu de 30
sed -i -E "s/registerProcessor\([\"'][^\"']+[\"']/registerProcessor(\"natif-$ID\"/" "$D/worklet.js"
sed -i 's#1 / 30#1 / 60#g' "$D/worklet.js"
# TextDecoder manque dans le fil audio de Chrome : quelques worklets s'en servent au chargement
sed -i '1i globalThis.TextDecoder ??= class { decode(b) { let s = ""; for (const c of b || []) s += String.fromCharCode(c); try { return decodeURIComponent(escape(s)); } catch (e) { return s; } } };' "$D/worklet.js"
grep -q "registerProcessor(\"natif-$ID\"" "$D/worklet.js" || { rm -rf "$D"; echec "nom de processeur introuvable"; }
E=""; [ -n "${NATIF_ECHANTILLONS:-}" ] && E=", \"echantillons\": \"outils/$NATIF_ECHANTILLONS\""
printf '{"wasm": "%s", "processeur": "natif-%s", "dialecte": "%s"%s}\n' "$(basename "$WASM")" "$ID" "$DIALECT" "$E" > "$D/natif.json"
echo "natif $ID : prêt ($DIALECT, $(basename "$WASM"), $(wc -c < "$WASM") octets)"
