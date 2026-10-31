# Autoria e fluxo de contribuição

Convenção de trabalho deste projecto:

- **Commits** — preparados com assistência de IA, com mensagens de commit em
  inglês e âmbito técnico descrito. O mantenedor revê cada commit antes de o
  aceitar e é o responsável único pelo conteúdo (alinhado com a `AI_POLICY.md`
  do FreeCAD, aplicada aqui por princípio).
- **Pushes, pull requests e publicações** — executados **exclusivamente pelo
  mantenedor humano** (GitHub: `melroleandro-solidreturn`). A ferramenta de IA
  nunca publica nem interage com o remoto por sua iniciativa.
- **Divulgação** — os pull requests upstream incluem nota de assistência de IA
  na descrição, com a verificação manual correspondente.
- **Idiomas** — mensagens de commit em inglês; documentação do repo em
  português de Portugal.

## Traduções (i18n)

As strings de UI usam `tr()` (`freecad.topografia.i18n`, contexto
`Topografia`, inglês como fonte). O catálogo pt-PT vive em
`freecad/topografia/resources/translations/topografia_pt-PT.ts`; depois
de o editar, recompilar os `.qm` (o `InitGui.py` carrega-os):

```bash
LRELEASE=/mnt/hypatia/FreeCAD/.pixi/envs/default/lib/qt6/bin/lrelease
cd freecad/topografia/resources/translations
"$LRELEASE" topografia_pt-PT.ts -qm topografia_pt-PT.qm
cp topografia_pt-PT.qm topografia_pt.qm   # variante para QLocale do sistema
```
