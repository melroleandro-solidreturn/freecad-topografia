# Topografia — base de dados topográficos para estradas (FreeCAD)

Módulo da **Fase 1** do plano de extensão do FreeCAD a projectos de estradas
(Civil 3D como referência funcional). Implementa o que a auditoria da Fase 0
mostrou não existir nem no núcleo, nem no Road Workbench, nem no CorridorRoad:
levantamento codificado disperso com breaklines e CSV pt-PT.

## Componentes

| Ficheiro | Papel |
|---|---|
| `freecad/topografia/csv_io.py` | Importador CSV/TXT: detecção automática de delimitador (`;` `,` tab `|`) e decimal (`,`/`.`), cabeçalhos PT/EN (`ponto;codigo;X;Y;cota`, `point,code,easting,northing,elevation`, …), mapeamento forçado por índices, **linhas rejeitadas com nº e motivo (zero perda silenciosa)**, utf-8-sig/latin-1 |
| `freecad/topografia/chaves.py` | Chaves de descrição (Description Keys): padrão → grupo/cor/breakline (`EP*` casa `EP`, `EP2`, …) |
| `freecad/topografia/triangulacao.py` | Delaunay (scipy) de pontos dispersos + **breaklines impostas**: atracamento de vértices colineares, densificação adaptativa, recuperação de arestas por flips, filtro opcional de aresta máxima |
| `freecad/topografia/objetos/levantamento.py` | Objecto `Points::FeaturePython`: `Model` com pontos absolutos (E,N,cota)+número+código; geometria LOCAL; origem absoluta em `Geolocalizacao` |
| `freecad/topografia/objetos/tin.py` | Objecto `Mesh::FeaturePython`: breaklines automáticas por código (pontos ordenados por número), `ModeloTIN` persistível (vértices/triângulos absolutos) para handoff (p.ex. CorridorRoad) |
| `freecad/topografia/objetos/curvas.py` | Objecto `Part::FeaturePython`: curvas de nível paramétricas (intervalo principal/intercalar), regeneram ao recomputar |

## Convenções

- **Coordenadas**: `Model` em absolutas (UTM, metros); geometria em LOCAL
  (absoluto − `Geolocalizacao.Base`) — mitiga o kernel Mesh em float com
  coordenadas grandes (auditado na Fase 0).
- **Breaklines por código**: os pontos de um código, ordenados por número de
  ponto, formam UMA polilinha (prática de levantamento sequencial). Use
  códigos distintos por linha (`LE_E`/`LE_D`, não `LE` para ambas as margens).
- **Atribuição**: LGPL-2.1-or-later (compatível com o núcleo do FreeCAD).

## Autoria e fluxo de contribuição

O código foi desenvolvido com assistência de IA sob revisão humana; commits
têm mensagens em inglês, e pushes/PRs/publicações são feitos apenas pelo
mantenedor — ver [CONTRIBUTING.md](CONTRIBUTING.md).

## LandXML (saída)

`freecad/topografia/landxml_export.py` escreve LandXML 1.2 com a TIN em
coordenadas ABSOLUTAS (`<Surfaces><Surface><Definition surfType="TIN">`) e os
pontos do levantamento com o código no `desc` (`<CgPoints>`, equivalente
funcional dos Point Groups). O formato é validado por round-trip contra o
importador LandXML do CorridorRoad (`scan_landxml_root` → `sample_xy` idêntico).

## Instalação

Instalação pelo Addon Manager (quando registado no catálogo), por `git clone` de
https://github.com/melroleandro-solidreturn/freecad-topografia para `~/.local/share/FreeCAD/<versão>/Mod/Topografia`, ou ligação simbólica do directório
para `~/.local/share/FreeCAD/<versão>/Mod/Topografia`. O `Init.py` faz o
bootstrap do namespace `freecad.topografia` e é seguro em consola
(FreeCADCmd); o `InitGui.py` regista o workbench **Topografia** com os
comandos: Import survey (CSV), Create terrain TIN, Contour lines,
Earthworks e Export LandXML — interface em inglês com catálogo pt-PT
(`freecad/topografia/resources/translations/`). Os comandos principais
abrem painéis de tarefa: o de importação mostra pré-visualização live
com o próprio motor (mapeamento/delimitador/decimal detectados e
sobreponíveis, linhas rejeitadas com motivo ANTES de importar); o de
TIN pré-marca as breaklines pelas chaves de descrição; o de
terraplenagem detecta TIN/alinhamento/perfil por varredura do documento
e exporta CSV e gráfico de mass haul; o export LandXML escreve um
ficheiro por objecto (sem sobreposições na multi-selecção).

## Testes

Correr dentro do FreeCADCmd (build 26.3-dev deste clone):

```bash
/mnt/hypatia/FreeCAD/build/debug/bin/FreeCADCmd tests/run_all.py
# 53 passed: csv_io, chaves, triangulação, objectos, curvas, terraplenagem,
#            LandXML round-trip, handoff CorridorRoad e painéis da GUI
```

O teste de handoff (`tests/test_prw_handoff.py`) prova que a TIN deste módulo
alimenta directamente o `TinSamplingService` do CorridorRoad via `TINSurface`
— a integração decidida no gate da Fase 0, sem ficheiro intermédio.

## Limitações conhecidas (v0.1.0)

- Construção da malha por `addFacet` em loop (~12,5 s para 10k pontos;
  a triangulação pura é 0,34 s) — optimizar com constructor por lista.
- Breakline = uma polilinha por código (ver convenções acima).
- GUI G1 concluída (painéis de tarefa, i18n); etiquetas de curvas, cores
  por chave de descrição e folha TechDraw ficam para a fase G2.
- LandXML de saída cobre superfície e pontos (alinhamentos/perfis ficam para o PRW).
