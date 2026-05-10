-- emoji-filter.lua
-- Filtro Lua para converter emojis Unicode em LaTeX nativo
-- SEM dependência do pacote 'emoji' (causa crash no luaotfload/AppleColorEmoji)
-- Usa símbolos LaTeX, textcomp e cores nativas

local emojis = {
  -- ✅ USADOS NO LIVRO (cap01.ipynb)
  ["🎓"] = "\\textbf{[grad]}",
  ["🔹"] = "$\\diamond$",
  ["🚀"] = "\\textbf{[launch]}",
  ["🤖"] = "\\textbf{[AI]}",
  ["🧪"] = "\\textbf{[exp]}",

  ["⚠"]  = "\\textbf{[!]}",
  ["▶"]  = "$\\triangleright$",
  ["👉"] = "$\\Rightarrow$",
  ["🐛"] = "\\textbf{[bug]}",

  -- 😀 ROSTOS E EMOÇÕES
  ["😀"] = "\\textbf{:)}",
  ["😁"] = "\\textbf{:D}",
  ["😂"] = "\\textbf{XD}",
  ["😃"] = "\\textbf{:)}",
  ["😄"] = "\\textbf{:)}",
  ["😅"] = "\\textbf{:)}",
  ["😆"] = "\\textbf{XD}",
  ["😇"] = "\\textbf{:)}",
  ["😊"] = "\\textbf{:)}",
  ["😋"] = "\\textbf{:P}",
  ["😎"] = "\\textbf{8)}",
  ["😍"] = "\\textbf{<3}",
  ["😢"] = "\\textbf{:(}",
  ["😭"] = "\\textbf{:((}",
  ["😡"] = "\\textbf{>:(}",
  ["😤"] = "\\textbf{>:(}",
  ["😱"] = "\\textbf{:O}",
  ["😴"] = "\\textbf{zzz}",
  ["🤔"] = "\\textbf{[?]}",
  ["🤩"] = "\\textbf{:*}",
  ["🥳"] = "\\textbf{[festa]}",
  ["🥺"] = "\\textbf{:'}",
  ["🤗"] = "\\textbf{[abraco]}",
  ["🤯"] = "\\textbf{[!?!]}",
  ["😬"] = "\\textbf{:/}",
  ["🙄"] = "\\textbf{[...]}", 

  -- 👍 GESTOS E PESSOAS
  ["👍"] = "\\textbf{[+1]}",
  ["👎"] = "\\textbf{[-1]}",
  ["👏"] = "\\textbf{[palmas]}",
  ["🙏"] = "\\textbf{[obg]}",
  ["👋"] = "\\textbf{[oi]}",
  ["✋"] = "\\textbf{[stop]}",
  ["🤝"] = "\\textbf{[ok]}",
  ["💪"] = "\\textbf{[forte]}",
  ["🧠"] = "\\textbf{[cerebro]}",
  ["👁"]  = "\\textbf{[olho]}",
  ["👀"] = "\\textbf{[olhos]}",
  ["👤"] = "\\textbf{[user]}",
  ["👥"] = "\\textbf{[users]}",
  ["🧑"] = "\\textbf{[pessoa]}",
  ["👩"] = "\\textbf{[pessoa]}",
  ["👨"] = "\\textbf{[pessoa]}",
  ["🧑‍💻"] = "\\textbf{[dev]}",
  ["👩‍💻"] = "\\textbf{[dev]}",
  ["👨‍💻"] = "\\textbf{[dev]}",
  ["🧑‍🎓"] = "\\textbf{[aluno]}",
  ["👩‍🏫"] = "\\textbf{[prof]}",
  ["👨‍🏫"] = "\\textbf{[prof]}",
  ["🧑‍🔬"] = "\\textbf{[pesq]}",

  -- 💡 OBJETOS E FERRAMENTAS
  ["💡"] = "\\textbf{[dica]}",
  ["🔍"] = "\\textbf{[busca]}",
  ["🔎"] = "\\textbf{[busca]}",
  ["🔧"] = "\\textbf{[config]}",
  ["🔨"] = "\\textbf{[build]}",
  ["⚙️"] = "\\textbf{[config]}",
  ["⚙"]  = "\\textbf{[config]}",
  ["🛠️"] = "\\textbf{[tools]}",
  ["📌"] = "\\textbf{[pin]}",
  ["📍"] = "\\textbf{[local]}",
  ["📎"] = "\\textbf{[clip]}",
  ["📏"] = "\\textbf{[regua]}",
  ["📐"] = "\\textbf{[esquadro]}",
  ["✂️"] = "\\textbf{[cortar]}",
  ["💾"] = "\\textbf{[salvar]}",
  ["💿"] = "\\textbf{[disco]}",
  ["📱"] = "\\textbf{[celular]}",
  ["💻"] = "\\textbf{[laptop]}",
  ["🖥️"] = "\\textbf{[PC]}",
  ["🖥"]  = "\\textbf{[PC]}",
  ["⌨️"] = "\\textbf{[teclado]}",
  ["📷"] = "\\textbf{[camera]}",
  ["📡"] = "\\textbf{[antena]}",
  ["🔋"] = "\\textbf{[bateria]}",
  ["🔌"] = "\\textbf{[plugue]}",

  -- 📚 EDUCAÇÃO E CIÊNCIA
  ["📚"] = "\\textbf{[livros]}",
  ["📖"] = "\\textbf{[ler]}",
  ["📝"] = "\\textbf{[nota]}",
  ["📓"] = "\\textbf{[caderno]}",
  ["📔"] = "\\textbf{[caderno]}",
  ["📒"] = "\\textbf{[caderno]}",
  ["📕"] = "\\textbf{[livro]}",
  ["📗"] = "\\textbf{[livro]}",
  ["📘"] = "\\textbf{[livro]}",
  ["📙"] = "\\textbf{[livro]}",
  ["📜"] = "\\textbf{[doc]}",
  ["📄"] = "\\textbf{[pagina]}",
  ["📃"] = "\\textbf{[pagina]}",
  ["📋"] = "\\textbf{[lista]}",
  ["📅"] = "\\textbf{[data]}",
  ["📆"] = "\\textbf{[data]}",
  ["🔬"] = "\\textbf{[micro]}",
  ["🔭"] = "\\textbf{[telescopio]}",
  ["🧬"] = "\\textbf{[DNA]}",
  ["🧫"] = "\\textbf{[cultura]}",
  ["🧲"] = "\\textbf{[ima]}",
  ["📊"] = "\\textbf{[grafico]}",
  ["📈"] = "$\\nearrow$",
  ["📉"] = "$\\searrow$",
  ["🐍"] = "\\textbf{[Python]}",

  -- ⚠️ SÍMBOLOS E SINAIS
  ["✅"] = "\\textbf{[ok]}",
  ["❌"] = "\\textbf{[x]}",
  ["❓"] = "\\textbf{[?]}",
  ["❗"] = "\\textbf{[!]}",
  ["⚠️"] = "\\textbf{[!]}",
  ["🚫"] = "\\textbf{[proib]}",
  ["🔴"] = "\\textcolor{red}{$\\bullet$}",
  ["🟠"] = "\\textcolor{orange}{$\\bullet$}",
  ["🟡"] = "\\textcolor{yellow}{$\\bullet$}",
  ["🟢"] = "\\textcolor{green}{$\\bullet$}",
  ["🔵"] = "\\textcolor{blue}{$\\bullet$}",
  ["🟣"] = "\\textcolor{violet}{$\\bullet$}",
  ["⚫"] = "$\\bullet$",
  ["⚪"] = "$\\circ$",
  ["🔶"] = "\\textcolor{orange}{$\\blacklozenge$}",
  ["🔷"] = "\\textcolor{blue}{$\\blacklozenge$}",
  ["🔸"] = "\\textcolor{orange}{$\\diamond$}",
  ["🔺"] = "$\\triangle$",
  ["🔻"] = "$\\triangledown$",
  ["▶️"] = "$\\triangleright$",
  ["⏩"] = "$\\gg$",
  ["⏪"] = "$\\ll$",
  ["🔁"] = "\\textbf{[loop]}",
  ["🔀"] = "\\textbf{[shuffle]}",
  ["➕"] = "$+$",
  ["➖"] = "$-$",
  ["✖️"] = "$\\times$",
  ["➗"] = "$\\div$",
  ["♾️"] = "$\\infty$",
  ["💯"] = "\\textbf{100\\%}",
  ["🔑"] = "\\textbf{[chave]}",
  ["🔒"] = "\\textbf{[bloq]}",
  ["🔓"] = "\\textbf{[desbloq]}",

  -- 🌐 NATUREZA
  ["🌍"] = "\\textbf{[mundo]}",
  ["🌎"] = "\\textbf{[mundo]}",
  ["🌏"] = "\\textbf{[mundo]}",
  ["🌐"] = "\\textbf{[web]}",
  ["🌱"] = "\\textbf{[inicio]}",
  ["☀️"] = "\\textbf{[sol]}",
  ["☀"]  = "\\textbf{[sol]}",
  ["🌙"] = "\\textbf{[noite]}",
  ["⭐"] = "$\\star$",
  ["🌟"] = "$\\bigstar$",
  ["⚡"] = "\\textbf{[!]}",
  ["🔥"] = "\\textbf{[hot]}",
  ["💧"] = "\\textbf{[agua]}",

  -- 🏆 PRÊMIOS
  ["🏆"] = "\\textbf{[trofeu]}",
  ["🥇"] = "\\textbf{[1o]}",
  ["🥈"] = "\\textbf{[2o]}",
  ["🥉"] = "\\textbf{[3o]}",
  ["🎯"] = "\\textbf{[alvo]}",
  ["🎲"] = "\\textbf{[jogo]}",
  ["🎮"] = "\\textbf{[game]}",
  ["🎨"] = "\\textbf{[arte]}",
  ["🎵"] = "\\textbf{[musica]}",
  ["🎶"] = "\\textbf{[musica]}",
  ["📣"] = "\\textbf{[anuncio]}",
  ["📢"] = "\\textbf{[aviso]}",

  -- 🤖 IA E TECNOLOGIA
  ["🦾"] = "\\textbf{[IA]}",
  ["💬"] = "\\textbf{[chat]}",
  ["💭"] = "\\textbf{[ideia]}",
  ["🔗"] = "\\textbf{[link]}",
  ["🛰️"] = "\\textbf{[satelite]}",
  ["🛸"] = "\\textbf{[nave]}",
  ["🔮"] = "\\textbf{[previsao]}",
  ["🧩"] = "\\textbf{[modulo]}",
  ["🧮"] = "\\textbf{[calc]}",

  -- ✍️ ESCRITA
  ["✍️"] = "\\textbf{[escrever]}",
  ["✏️"] = "\\textbf{[editar]}",
  ["📧"] = "\\textbf{[email]}",
  ["📦"] = "\\textbf{[pkg]}",
  ["🏷️"] = "\\textbf{[label]}",

  -- EXTRAS USADOS NO LIVRO
  ["🖼"]  = "\\textbf{[img]}",
  ["🏁"]  = "\\textbf{[fim]}",
  ["⬛"]  = "$\\blacksquare$",
  ["◻"]   = "$\\square$",
  ["░"]   = "\\texttt{[light]}",
  ["▒"]   = "\\texttt{[med]}",
  ["▓"]   = "\\texttt{[dark]}",
  ["█"]   = "$\\blacksquare$",
  ["🟥"]  = "\\textcolor{red}{$\\blacksquare$}",
  ["🟩"]  = "\\textcolor{green}{$\\blacksquare$}",
  ["🟦"]  = "\\textcolor{blue}{$\\blacksquare$}",
  ["☕"]  = "\\textbf{[cafe]}",
  ["∞"]   = "$\\infty$",
  ["💪"]  = "\\textbf{[ok]}",
  ["🤝"]  = "\\textbf{[ok]}",

  -- ➡️ SETAS
  ["➡️"] = "$\\rightarrow$",
  ["⬅️"] = "$\\leftarrow$",
  ["⬆️"] = "$\\uparrow$",
  ["⬇️"] = "$\\downarrow$",
  ["↗️"] = "$\\nearrow$",
  ["↘️"] = "$\\searrow$",
  ["↙️"] = "$\\swarrow$",
  ["↖️"] = "$\\nwarrow$",
  ["↩️"] = "$\\hookleftarrow$",
  ["↪️"] = "$\\hookrightarrow$",
  ["🔄"] = "\\textbf{[atualizar]}",
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