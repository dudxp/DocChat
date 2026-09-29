"""Gera os PDFs de exemplo usados na demonstração e nos testes.

Os documentos são fictícios. Rodar de novo só é necessário se o texto mudar:
    pip install reportlab && python samples/generate_samples.py
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

HERE = Path(__file__).parent

MANUAL = [
    (
        "Manual de Operação — Esteira Transportadora ET-200",
        [
            "Este manual descreve a instalação, a operação e a manutenção da esteira transportadora ET-200, "
            "fabricada pela empresa fictícia Transmec Equipamentos. Leia o documento inteiro antes de ligar o "
            "equipamento pela primeira vez.",
            "A ET-200 foi projetada para o transporte horizontal de caixas e volumes de até 50 kg por metro "
            "linear em linhas de embalagem e expedição. O uso com produtos a granel ou em ambientes com risco "
            "de explosão não é permitido.",
            "Revisão do documento: 3.2. Em caso de dúvidas, contate o suporte técnico pelo telefone 0800 000 2020, "
            "de segunda a sexta, das 8h às 18h.",
        ],
    ),
    (
        "1. Especificações técnicas",
        [
            "Comprimento útil: 6 metros, com módulos de extensão de 2 metros. Largura da correia: 600 mm.",
            "Motor: trifásico de 1,5 kW (2 cv), 380 V, 60 Hz, com grau de proteção IP55. O acionamento é feito "
            "por inversor de frequência, que permite ajustar a velocidade da correia entre 0,2 e 1,5 metro por segundo.",
            "Capacidade de carga: até 50 kg por metro linear, com carga máxima total de 300 kg distribuída.",
            "Temperatura de operação: de 0 °C a 45 °C. Umidade relativa máxima: 85%, sem condensação.",
            "Nível de ruído em operação: inferior a 70 dB(A) medido a 1 metro do equipamento.",
        ],
    ),
    (
        "2. Instalação",
        [
            "A esteira deve ser instalada sobre piso nivelado, com desnível máximo de 2 mm por metro. "
            "Use os pés reguláveis para corrigir pequenas diferenças e fixe a estrutura ao piso com chumbadores M10.",
            "A alimentação elétrica deve ser feita por um eletricista qualificado, com disjuntor dedicado de 10 A "
            "e aterramento conforme a norma NBR 5410. Nunca ligue a esteira em tomadas comuns.",
            "Antes da primeira partida, confira o tensionamento da correia: ao pressionar o centro do vão com a mão, "
            "a flecha deve ficar entre 10 e 15 mm.",
        ],
    ),
    (
        "3. Operação",
        [
            "Para ligar a esteira, gire a chave geral para a posição I, confirme que não há pessoas ou objetos sobre "
            "a correia e pressione o botão verde de partida. A partida é suave e leva cerca de 3 segundos.",
            "A velocidade é ajustada pelo potenciômetro do painel frontal. Para caixas instáveis ou empilhadas, "
            "recomenda-se não passar de 0,8 metro por segundo.",
            "O botão de emergência, de cor vermelha e formato cogumelo, interrompe imediatamente o motor. "
            "Após acioná-lo, gire o botão no sentido horário para destravar e só então pressione o botão azul de rearme.",
            "Nunca deixe a esteira funcionando vazia por mais de 30 minutos seguidos, para evitar o desgaste da correia.",
        ],
    ),
    (
        "4. Manutenção preventiva",
        [
            "Diariamente: limpe a correia com pano úmido e detergente neutro e verifique se há objetos presos nos roletes.",
            "Semanalmente: confira o alinhamento da correia e o aperto dos parafusos da estrutura.",
            "A cada 500 horas de operação: lubrifique os rolamentos dos tambores com graxa à base de lítio, "
            "aplicando duas bombadas em cada graxeira.",
            "A cada 2.000 horas de operação: troque o óleo do redutor. Utilize óleo sintético ISO VG 220, "
            "com volume de 0,8 litro.",
            "A garantia do equipamento é de 12 meses a partir da data da nota fiscal e perde a validade se a "
            "manutenção preventiva não for registrada no livro de manutenção.",
        ],
    ),
    (
        "5. Solução de problemas",
        [
            "A correia desliza para um dos lados: ajuste os parafusos esticadores do tambor de retorno, meia volta "
            "de cada vez, sempre no lado para onde a correia está correndo.",
            "O motor não parte: verifique se o botão de emergência está destravado, se o disjuntor está ligado e se o "
            "inversor exibe algum código de falha no display.",
            "Código de falha F02 no inversor: sobrecorrente. Reduza a carga sobre a correia e confira se algum rolete "
            "está travado. Código F05: sobretemperatura do inversor, verifique a ventilação do painel.",
            "Ruído metálico durante a operação: indica rolamento danificado. Pare o equipamento e substitua o rolamento "
            "antes de voltar a operar.",
        ],
    ),
]

POLICY = [
    (
        "Política de Férias e Benefícios — Empresa Exemplo Ltda.",
        [
            "Esta política se aplica a todos os colaboradores contratados em regime CLT pela Empresa Exemplo Ltda., "
            "organização fictícia criada para fins de demonstração.",
            "A área de Pessoas é responsável por manter este documento atualizado. A versão vigente entrou em vigor "
            "em 1º de março.",
        ],
    ),
    (
        "1. Férias",
        [
            "Cada colaborador tem direito a 30 dias de férias após completar 12 meses de trabalho, chamados de período aquisitivo.",
            "As férias podem ser divididas em até três períodos, desde que um deles tenha pelo menos 14 dias corridos "
            "e os demais não sejam inferiores a 5 dias corridos cada.",
            "A solicitação deve ser feita no portal do colaborador com antecedência mínima de 45 dias e aprovada pelo gestor imediato.",
            "É possível converter um terço das férias em abono pecuniário, desde que o pedido seja feito até 15 dias "
            "antes do fim do período aquisitivo.",
        ],
    ),
    (
        "2. Benefícios",
        [
            "Vale-refeição: crédito mensal de R$ 900,00, carregado no primeiro dia útil de cada mês.",
            "Plano de saúde: cobertura nacional com coparticipação de 20% em consultas e exames; o colaborador pode incluir "
            "cônjuge e filhos de até 24 anos como dependentes.",
            "Auxílio home office: R$ 150,00 por mês para quem trabalha remotamente pelo menos três dias por semana.",
            "Auxílio educação: reembolso de até 50% da mensalidade de cursos de graduação ou pós-graduação relacionados "
            "à função, limitado a R$ 1.000,00 por mês, após seis meses de empresa.",
        ],
    ),
    (
        "3. Trabalho remoto e jornada",
        [
            "O modelo de trabalho é híbrido: a presença no escritório é obrigatória às terças e quintas-feiras.",
            "A jornada padrão é de 40 horas semanais, com banco de horas compensável em até seis meses.",
            "Horas extras precisam de aprovação prévia do gestor e são pagas com adicional de 50% em dias úteis e de 100% "
            "aos domingos e feriados.",
        ],
    ),
]

SALARIES = [
    (
        "Faixas Salariais e Critérios de Promoção — Empresa Exemplo Ltda.",
        [
            "Documento confidencial da área de Pessoas. Os valores abaixo são fictícios e existem apenas para "
            "demonstrar o controle de acesso do DocChat: só usuários da área RH devem conseguir consultá-lo.",
            "Revisão anual das faixas: em fevereiro, com base na pesquisa salarial de mercado.",
        ],
    ),
    (
        "1. Faixas por cargo",
        [
            "Técnico de manutenção I: de R$ 3.800,00 a R$ 4.900,00.",
            "Técnico de manutenção II: de R$ 4.900,00 a R$ 6.300,00.",
            "Engenheiro de automação pleno: de R$ 9.500,00 a R$ 12.800,00.",
            "Analista de estoque: de R$ 4.200,00 a R$ 5.600,00.",
            "A promoção entre níveis exige pelo menos 18 meses no nível atual e avaliação de desempenho igual "
            "ou superior a 'atende plenamente' nos dois últimos ciclos.",
        ],
    ),
]


def build(path: Path, sections: list[tuple[str, list[str]]]) -> None:
    styles = getSampleStyleSheet()
    story = []
    for i, (title, paragraphs) in enumerate(sections):
        if i:
            story.append(PageBreak())
        story.append(Paragraph(title, styles["Title"] if i == 0 else styles["Heading1"]))
        story.append(Spacer(1, 12))
        for text in paragraphs:
            story.append(Paragraph(text, styles["BodyText"]))
            story.append(Spacer(1, 8))
    SimpleDocTemplate(str(path), pagesize=A4, title=sections[0][0], author="DocChat (exemplo)").build(story)


if __name__ == "__main__":
    build(HERE / "manual-esteira-et200.pdf", MANUAL)
    build(HERE / "politica-ferias-beneficios.pdf", POLICY)
    build(HERE / "faixas-salariais-rh.pdf", SALARIES)
    print("PDFs gerados em", HERE)
