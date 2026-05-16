-- emoji-filter.lua
-- Filtro Lua para converter emojis Unicode em comandos LaTeX
-- Usa \emoji{} do pacote 'emoji' para a maioria
-- Usa LaTeX nativo para emojis que causam crash no luaotfload/AppleColorEmoji:
--   ▶ (play-button), ⚙ (gear), ☀ (sun), ⚠ (warning) etc.

local emojis = {
  -- ✅ USADOS NO LIVRO
  ["🎓"] = "\\emoji{graduation-cap}",
  ["🔹"] = "\\emoji{small-blue-diamond}",
  ["🚀"] = "\\emoji{rocket}",
  ["🤖"] = "\\emoji{robot}",
  ["🧪"] = "\\emoji{test-tube}",

  -- ⚠ PROBLEMÁTICOS — LaTeX nativo (causam crash no luaotfload com AppleColorEmoji)
  ["▶"]   = "$\\triangleright$",
  ["⚙"]   = "\\S{}",
  ["⚙️"]  = "\\S{}",
  ["☀"]   = "$\\odot$",
  ["☀️"]  = "$\\odot$",
  ["⚠"]   = "\\emoji{warning}",
  ["⚠️"]  = "\\emoji{warning}",
  ["∞"]   = "$\\infty$",
  ["░"]   = "\\texttt{[~]}",
  ["▒"]   = "\\texttt{[=]}",
  ["▓"]   = "\\texttt{[\\#]}",
  ["█"]   = "$\\blacksquare$",
  ["⬛"]  = "$\\blacksquare$",
  ["◻"]   = "$\\square$",
  ["🟥"]  = "\\textcolor{red}{$\\blacksquare$}",
  ["🟩"]  = "\\textcolor{green}{$\\blacksquare$}",
  ["🟦"]  = "\\textcolor{blue}{$\\blacksquare$}",
  ["📈"]  = "$\\nearrow$",
  ["📉"]  = "$\\searrow$",

  -- 😀 ROSTOS E EMOÇÕES
  ["😀"] = "\\emoji{grinning}",
  ["😁"] = "\\emoji{beaming-face-with-smiling-eyes}",
  ["😂"] = "\\emoji{face-with-tears-of-joy}",
  ["😃"] = "\\emoji{grinning-face-with-big-eyes}",
  ["😄"] = "\\emoji{grinning-face-with-smiling-eyes}",
  ["😅"] = "\\emoji{grinning-face-with-sweat}",
  ["😆"] = "\\emoji{grinning-squinting-face}",
  ["😇"] = "\\emoji{smiling-face-with-halo}",
  ["😊"] = "\\emoji{smiling-face-with-smiling-eyes}",
  ["😋"] = "\\emoji{face-savoring-food}",
  ["😎"] = "\\emoji{smiling-face-with-sunglasses}",
  ["😍"] = "\\emoji{smiling-face-with-heart-eyes}",
  ["😢"] = "\\emoji{crying-face}",
  ["😭"] = "\\emoji{loudly-crying-face}",
  ["😡"] = "\\emoji{enraged-face}",
  ["😤"] = "\\emoji{face-with-steam-from-nose}",
  ["😱"] = "\\emoji{face-screaming-in-fear}",
  ["😴"] = "\\emoji{sleeping-face}",
  ["🤔"] = "\\emoji{thinking-face}",
  ["🤩"] = "\\emoji{star-struck}",
  ["🥳"] = "\\emoji{partying-face}",
  ["🥺"] = "\\emoji{pleading-face}",
  ["🤗"] = "\\emoji{smiling-face-with-open-hands}",
  ["🤯"] = "\\emoji{exploding-head}",
  ["😬"] = "\\emoji{grimacing-face}",
  ["🙄"] = "\\emoji{face-with-rolling-eyes}",

  -- 👍 GESTOS E PESSOAS
  ["👍"] = "\\emoji{thumbs-up}",
  ["👎"] = "\\emoji{thumbs-down}",
  ["👏"] = "\\emoji{clapping-hands}",
  ["🙏"] = "\\emoji{folded-hands}",
  ["👋"] = "\\emoji{waving-hand}",
  ["✋"] = "\\emoji{raised-hand}",
  ["🤝"] = "\\emoji{handshake}",
  ["💪"] = "\\emoji{flexed-biceps}",
  ["🧠"] = "\\emoji{brain}",
  ["👁"]  = "\\emoji{eye}",
  ["👀"] = "\\emoji{eyes}",
  ["👤"] = "\\emoji{bust-in-silhouette}",
  ["👥"] = "\\emoji{busts-in-silhouette}",
  ["🧑"] = "\\emoji{person}",
  ["👩"] = "\\emoji{woman}",
  ["👨"] = "\\emoji{man}",
  ["🧑‍💻"] = "\\emoji{technologist}",
  ["👩‍💻"] = "\\emoji{woman-technologist}",
  ["👨‍💻"] = "\\emoji{man-technologist}",
  ["🧑‍🎓"] = "\\emoji{student}",
  ["👩‍🏫"] = "\\emoji{woman-teacher}",
  ["👨‍🏫"] = "\\emoji{man-teacher}",
  ["🧑‍🔬"] = "\\emoji{scientist}",

  -- 💡 OBJETOS E FERRAMENTAS
  ["💡"] = "\\emoji{light-bulb}",
  ["🔍"] = "\\emoji{magnifying-glass-tilted-left}",
  ["🔎"] = "\\emoji{magnifying-glass-tilted-right}",
  ["🔧"] = "\\emoji{wrench}",
  ["🔨"] = "\\emoji{hammer}",
  ["🛠️"] = "\\emoji{hammer-and-wrench}",
  ["📌"] = "\\emoji{pushpin}",
  ["📍"] = "\\emoji{round-pushpin}",
  ["📎"] = "\\emoji{paperclip}",
  ["📏"] = "\\emoji{straight-ruler}",
  ["📐"] = "\\emoji{triangular-ruler}",
  ["💾"] = "\\emoji{floppy-disk}",
  ["💿"] = "\\emoji{optical-disk}",
  ["📱"] = "\\emoji{mobile-phone}",
  ["💻"] = "\\emoji{computer}",
  ["🖥️"] = "\\emoji{desktop-computer}",
  ["🖥"]  = "\\emoji{desktop-computer}",
  ["📷"] = "\\emoji{camera}",
  ["📡"] = "\\emoji{satellite-antenna}",
  ["🔋"] = "\\emoji{battery}",
  ["🔌"] = "\\emoji{electric-plug}",

  -- 📚 EDUCAÇÃO E CIÊNCIA
  ["📚"] = "\\emoji{books}",
  ["📖"] = "\\emoji{open-book}",
  ["📝"] = "\\emoji{memo}",
  ["📓"] = "\\emoji{notebook}",
  ["📔"] = "\\emoji{notebook-with-decorative-cover}",
  ["📒"] = "\\emoji{ledger}",
  ["📕"] = "\\emoji{closed-book}",
  ["📗"] = "\\emoji{green-book}",
  ["📘"] = "\\emoji{blue-book}",
  ["📙"] = "\\emoji{orange-book}",
  ["📜"] = "\\emoji{scroll}",
  ["📄"] = "\\emoji{page-facing-up}",
  ["📃"] = "\\emoji{page-with-curl}",
  ["📋"] = "\\emoji{clipboard}",
  ["📅"] = "\\emoji{calendar}",
  ["📆"] = "\\emoji{tear-off-calendar}",
  ["🔬"] = "\\emoji{microscope}",
  ["🔭"] = "\\emoji{telescope}",
  ["🧬"] = "\\emoji{dna}",
  ["🧫"] = "\\emoji{petri-dish}",
  ["🧲"] = "\\emoji{magnet}",
  ["📊"] = "\\emoji{bar-chart}",
  ["🐍"] = "\\emoji{snake}",

  -- ⚠️ SÍMBOLOS E SINAIS
  ["✅"] = "\\emoji{check-mark-button}",
  ["❌"] = "\\emoji{cross-mark}",
  ["❓"] = "\\emoji{question-mark}",
  ["❗"] = "\\emoji{exclamation-mark}",
  ["🚫"] = "\\emoji{prohibited}",
  ["🔴"] = "\\emoji{red-circle}",
  ["🟠"] = "\\emoji{orange-circle}",
  ["🟡"] = "\\emoji{yellow-circle}",
  ["🟢"] = "\\emoji{green-circle}",
  ["🔵"] = "\\emoji{blue-circle}",
  ["🟣"] = "\\emoji{purple-circle}",
  ["⚫"] = "\\emoji{black-circle}",
  ["⚪"] = "\\emoji{white-circle}",
  ["🔶"] = "\\emoji{large-orange-diamond}",
  ["🔷"] = "\\emoji{large-blue-diamond}",
  ["🔸"] = "\\emoji{small-orange-diamond}",
  ["🔺"] = "\\emoji{red-triangle-pointed-up}",
  ["🔻"] = "\\emoji{red-triangle-pointed-down}",
  ["⏩"] = "\\emoji{fast-forward-button}",
  ["⏪"] = "\\emoji{fast-reverse-button}",
  ["🔁"] = "\\emoji{repeat-button}",
  ["🔀"] = "\\emoji{shuffle-tracks-button}",
  ["➕"] = "\\emoji{plus}",
  ["➖"] = "\\emoji{minus}",
  ["💯"] = "\\emoji{hundred-points}",
  ["🔑"] = "\\emoji{key}",
  ["🔒"] = "\\emoji{locked}",
  ["🔓"] = "\\emoji{unlocked}",
  ["🏁"] = "\\emoji{chequered-flag}",
  ["🖼"] = "\\emoji{framed-picture}",
  ["☕"] = "\\emoji{hot-beverage}",
  ["📦"] = "\\emoji{package}",

  -- 🌐 NATUREZA
  ["🌍"] = "\\emoji{earth-africa}",
  ["🌎"] = "\\emoji{earth-americas}",
  ["🌏"] = "\\emoji{earth-asia}",
  ["🌐"] = "\\emoji{globe-with-meridians}",
  ["🌱"] = "\\emoji{seedling}",
  ["🌙"] = "\\emoji{crescent-moon}",
  ["⭐"] = "\\emoji{star}",
  ["🌟"] = "\\emoji{glowing-star}",
  ["⚡"] = "\\emoji{lightning}",
  ["🔥"] = "\\emoji{fire}",
  ["💧"] = "\\emoji{droplet}",
  ["🌊"] = "\\emoji{water-wave}",

  -- 🏆 PRÊMIOS
  ["🏆"] = "\\emoji{trophy}",
  ["🥇"] = "\\emoji{1st-place-medal}",
  ["🥈"] = "\\emoji{2nd-place-medal}",
  ["🥉"] = "\\emoji{3rd-place-medal}",
  ["🎯"] = "\\emoji{bullseye}",
  ["🎲"] = "\\emoji{game-die}",
  ["🎮"] = "\\emoji{video-game}",
  ["🎨"] = "\\emoji{artist-palette}",
  ["🎵"] = "\\emoji{musical-note}",
  ["🎶"] = "\\emoji{musical-notes}",
  ["📣"] = "\\emoji{megaphone}",
  ["📢"] = "\\emoji{loudspeaker}",

  -- 🤖 IA E TECNOLOGIA
  ["🦾"] = "\\emoji{mechanical-arm}",
  ["💬"] = "\\emoji{speech-balloon}",
  ["💭"] = "\\emoji{thought-balloon}",
  ["🔗"] = "\\emoji{link}",
  ["🛰️"] = "\\emoji{satellite}",
  ["🛸"] = "\\emoji{flying-saucer}",
  ["🔮"] = "\\emoji{crystal-ball}",
  ["🧩"] = "\\emoji{puzzle-piece}",
  ["🧮"] = "\\emoji{abacus}",

  -- ✍️ ESCRITA
  ["✏️"] = "\\emoji{pencil}",
  ["📧"] = "\\emoji{e-mail}",
  ["🏷️"] = "\\emoji{label}",
  ["👉"] = "\\emoji{backhand-index-pointing-right}",
  ["🐛"] = "\\emoji{bug}",

  -- ➡️ SETAS
  ["➡️"] = "\\emoji{right-arrow}",                     -- Também mapeado antes como: "$\\rightarrow$"
  ["⬅️"] = "\\emoji{left-arrow}",
  ["⬆️"] = "\\emoji{up-arrow}",
  ["⬇️"] = "\\emoji{down-arrow}",
  ["🔽"] = "\\emoji{down-arrow-button}",               -- Mudado para emoji (antigo: "$\\downarrow$")
  ["↩️"] = "\\emoji{right-arrow-curving-left}",
  ["↪️"] = "\\emoji{left-arrow-curving-right}",
  ["🔄"] = "\\emoji{counterclockwise-arrows-button}",
  ["▶️"] = "\\emoji{play-button}",                     -- Também mapeado antes como: "$\\triangleright$"

  -- Garante emojis do TestSuite mesmo que não estejam no lua

  ["✔️"] = "\\emoji{check-mark-button}",
  ["📥"] =  "\\emoji{inbox-tray}",
  ["📤"] =  "\\emoji{outbox-tray}",
  ["🎉"] =  "\\emoji{party-popper}",
  ["⏱️"] =  "\\emoji{stopwatch}",
  ["💥"] =  "\\emoji{collision}",

  ["✓"] = "\\emoji{check-mark}",
  ["✔"] = "\\emoji{heavy-check-mark}",  
  ["⚠"] = "\\emoji{warning}",
  ["📸"] = "\\emoji{camera-with-flash}",
  ["👉"] = "\\emoji{backhand-index-pointing-right}",
  ["📖"] = "\\emoji{open-book}",
  ["🐛"] = "\\emoji{bug}",
  ["🤝"] = "\\emoji{handshake}",
  ["🔧"] = "\\emoji{wrench}",
    
}


-- Função principal do filtro
function Str(el)
  if FORMAT ~= "latex" then return nil end

  local result = {}
  local has_emoji = false
  local pending = ""

  for _, cp in utf8.codes(el.text) do
    if cp == 0xFE0F or cp == 0xFE0E then
      -- variation selector: ignora
    else
      local char = utf8.char(cp)
      if emojis[char] then
        if pending ~= "" then
          table.insert(result, pandoc.Str(pending))
          pending = ""
        end
        table.insert(result, pandoc.RawInline("latex", emojis[char]))
        has_emoji = true
      else
        pending = pending .. char
      end
    end
  end

  if pending ~= "" then
    table.insert(result, pandoc.Str(pending))
  end

  if has_emoji then
    return result
  end
end

 
function RawInline(el)
  if el.format == "html" and el.text:match("<br") then
    if FORMAT:match("latex") then
      return pandoc.RawInline("latex", "\\newline{}")
    else
      return pandoc.LineBreak()
    end
  end
end