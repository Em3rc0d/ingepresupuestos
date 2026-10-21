# Glossário espanhol (Peru) → português (Brasil)

Termos da interface do IngePresupuestos em `pt_BR.json`. O programa nasceu no
Peru e usa o jargão de lá (S10, PowerCost, Delphin); aqui está o equivalente
brasileiro escolhido para cada termo e o porquê. **Victor, se algum termo soar
estranho para um orçamentista brasileiro, anote ao lado: trocar é só editar o
JSON.** Regra: o mesmo termo em espanhol vai SEMPRE para o mesmo termo em
português.

Os relatórios (PDF, Excel, Word) **não** são traduzidos: saem no idioma do
projeto. Só a interface muda.

## Orçamento e composições

| Espanhol (Peru) | Português (Brasil) | Nota |
|---|---|---|
| Presupuesto | Orçamento | |
| Sub-presupuesto | Suborçamento | Bloco do orçamento com aba própria (ex.: estrutura, instalações). |
| Partida | Serviço | Linha do orçamento com quantidade e preço. Não usamos «item» para não confundir com a coluna **Item** (o código 01.02.03). |
| Título (de partidas) | Etapa | Agrupador da EAP (01 OBRAS PROVISÓRIAS…). «Agregar título» → «Adicionar etapa». |
| Ítem | Item | O código hierárquico 01.02.03. |
| ACU — Análisis de Costos Unitarios | CPU — Composição de Preço Unitário | «ACU» sozinho → «CPU». |
| Costo unitario (CU) | Custo unitário (CU) | |
| Biblioteca CU / de costos unitarios | Biblioteca de composições | |
| Precio unitario (PU) | Preço unitário (PU) | |
| Parcial | Parcial | Quantidade × preço. |
| Costo directo (CD) | Custo direto (CD) | |
| Insumo / recurso | Insumo | |
| Mano de obra (MO) | Mão de obra (MO) | Os códigos de tipo MO/MAT/EQ/SC **não** mudam: são dados. |
| Materiales (MAT) | Materiais (MAT) | |
| Equipos (EQ) | Equipamentos (EQ) | |
| Sub-contratos / Servicios (SC) | Subempreitadas / Serviços (SC) | |
| Cuadrilla | Equipe | Nº de trabalhadores/equipamentos da composição (0,1 encarregado; 1 pedreiro…). |
| Rendimiento | Produtividade | Produção por dia (m²/dia). A quantidade de MO = equipe ÷ produtividade × jornada. |
| Jornada laboral | Jornada de trabalho | Horas por dia (8). |
| Cantidad | Quantidade | |
| Unidad | Unidade | |
| Partida global (glb) | Serviço por verba (vb) | Preço fechado, sem equipe. |
| Metrado | Quantitativo | |
| Metrados / Hoja de metrados | Quantitativos / Memória de cálculo | |
| Planilla de metrados | Planilha de quantitativos | |
| Acero (metrado de acero) | Armadura (aço) | |
| Pie de presupuesto | Fechamento do orçamento | As linhas que vêm depois do custo direto (despesas, lucro, impostos). **Não** usamos «BDI» ainda: o programa calcula linha por linha, não um percentual único. |
| Gastos generales (GG) | Despesas gerais (DG) | |
| Utilidad | Lucro | |
| IGV | IGV | Imposto peruano sobre vendas (18 %). Mantido o nome; o usuário pode renomear a linha no fechamento. |
| Subtotal | Subtotal | |
| Especificaciones técnicas | Especificações técnicas | |
| Memoria descriptiva | Memorial descritivo | |
| Expediente técnico | Projeto executivo | |
| Modalidad: administración directa / contrata | Administração direta / empreitada | |
| Plazo de obra | Prazo de execução | |
| Proyecto | Projeto | |
| Portafolio | Portfólio | |

## Cronograma e controle de obra

| Espanhol (Peru) | Português (Brasil) | Nota |
|---|---|---|
| Cronograma | Cronograma | |
| Cronograma valorizado | Cronograma físico-financeiro | |
| Diagrama de Gantt | Gráfico de Gantt | |
| Ruta crítica | Caminho crítico | |
| Predecesoras | Predecessoras | |
| Hito | Marco | |
| Curva S | Curva S | |
| Adquisiciones / calendario de adquisiciones | Aquisições / cronograma de compras | |
| Control de obra | Controle de obra | |
| Valorización | Medição | O documento mensal que mede e paga o executado. |
| Metrado del período | Quantidade medida no período | |
| Cuaderno de obra / parte diario | Diário de obra | |
| Almacén | Almoxarifado | |
| Kárdex | Ficha de estoque | |
| Requerimiento | Requisição | |
| Liquidación | Liquidação | |
| Fórmula polinómica | Fórmula polinomial de reajuste | Regra peruana (D.S. 011-79-VC). |
| Índices INEI / índice unificado | Índices INEI / índice unificado | INEI = o IBGE do Peru; mantido o nome porque é a fonte real dos dados. |
| Monomio | Monômio | |
| Reajuste | Reajuste | |

## Interface

| Espanhol | Português (Brasil) |
|---|---|
| Inicio | Início |
| Configuración | Configurações |
| Acerca de | Sobre |
| Centro de reportes / reporte | Central de relatórios / relatório |
| Catálogo de insumos | Catálogo de insumos |
| Agregar | Adicionar |
| Guardar | Salvar |
| Eliminar | Excluir |
| Deshacer / Rehacer | Desfazer / Refazer |
| Vista previa | Visualizar / pré-visualização |
| Copia de seguridad (backup) | Backup / cópia de segurança |
| En elaboración (estado) | Em elaboração |
| Asistente Tuxia | Assistente Tuxia |
