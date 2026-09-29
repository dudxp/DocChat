"""Testes que não precisam de banco: chunking, citações, métricas e o juiz."""

from types import SimpleNamespace

from conftest import MANUAL

from app.evaluation import citation_hit, parse_judge, retrieval_metrics, summarize, token_f1
from app.ingestion import clean_text, extract_pages, split_pages
from app.providers import HashingEmbeddings
from app.rag import Answer, extract_citations, format_context
from app.retrieval import RetrievedChunk, build_or_tsquery, reciprocal_rank_fusion


def chunk(page: int, document_id: int = 1) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=page, document_id=document_id, filename="a.pdf", page=page, content="x", similarity=0.5, score=0.1
    )


class TestIngestion:
    def test_extracts_one_text_per_page(self):
        pages = extract_pages(MANUAL.read_bytes())
        assert len(pages) == 6
        assert "1,5 kW" in pages[1]

    def test_chunks_never_cross_pages(self):
        pages = ["a " * 800, "", "b " * 300]
        chunks = split_pages(pages, chunk_size=500, chunk_overlap=50)
        assert {c.page for c in chunks} == {1, 3}
        assert all(set(c.content.split()) == {"a"} for c in chunks if c.page == 1)
        assert [c.index for c in chunks] == list(range(len(chunks)))

    def test_clean_text_rejoins_hyphenated_words_and_drops_nul(self):
        assert clean_text("manu-\ntenção\x00  preventiva") == "manutenção preventiva"


class TestCitations:
    def test_extracts_unique_citations_in_order(self):
        assert extract_citations("A [2]. B [1][2]. C [2]", 3) == [2, 1]

    def test_ignores_numbers_outside_the_sources(self):
        assert extract_citations("Veja [0] e [7] e [3]", 3) == [3]

    def test_context_numbers_sources_from_one(self):
        context = format_context([chunk(4), chunk(9)])
        assert context.startswith("[1] (documento: a.pdf, página 4)")
        assert "[2] (documento: a.pdf, página 9)" in context


class TestRetrievalHelpers:
    def test_tsquery_uses_or_between_terms(self):
        assert build_or_tsquery("Qual a pressão máxima?") == "máxima | pressão | qual"

    def test_tsquery_of_punctuation_only_is_none(self):
        assert build_or_tsquery("?? !") is None

    def test_rrf_rewards_items_present_in_both_rankings(self):
        scores = reciprocal_rank_fusion([[1, 2, 3], [3, 4]])
        assert max(scores, key=scores.get) == 3

    def test_hashing_embeddings_are_normalized_and_deterministic(self):
        emb = HashingEmbeddings(64)
        a, b = emb.embed_query("motor trifásico"), emb.embed_query("motor trifásico")
        assert a == b
        assert abs(sum(v * v for v in a) - 1.0) < 1e-9


class TestMetrics:
    case = SimpleNamespace(document_id=1, expected_page=5)

    def answer(self, pages: list[int], cited: list[int]) -> Answer:
        return Answer(question="q", search_query="q", answer="", sources=[chunk(p) for p in pages], cited=cited)

    def test_reciprocal_rank_uses_position_of_first_correct_chunk(self):
        assert retrieval_metrics(self.answer([2, 5, 5], []), self.case) == (True, 0.5)

    def test_miss_scores_zero(self):
        assert retrieval_metrics(self.answer([1, 2], []), self.case) == (False, 0.0)

    def test_same_page_in_another_document_is_not_a_hit(self):
        answer = Answer(question="q", search_query="q", answer="", sources=[chunk(5, document_id=2)])
        assert retrieval_metrics(answer, self.case) == (False, 0.0)

    def test_case_without_page_is_not_measured(self):
        case = SimpleNamespace(document_id=None, expected_page=None)
        assert retrieval_metrics(self.answer([1], []), case) == (None, None)
        assert citation_hit(self.answer([1], [1]), case) is None

    def test_citation_hit_only_when_the_cited_source_is_the_right_page(self):
        assert citation_hit(self.answer([5, 2], [1]), self.case) is True
        assert citation_hit(self.answer([5, 2], [2]), self.case) is False

    def test_token_f1_ignores_accents_and_citation_marks(self):
        assert token_f1("Óleo sintético ISO VG 220 [1]", "oleo sintetico ISO VG 220") == 1.0
        assert token_f1("nada a ver", "óleo sintético") == 0.0

    def test_summary_skips_unmeasured_values(self):
        results = [
            SimpleNamespace(
                retrieval_hit=True,
                reciprocal_rank=1.0,
                citation_hit=True,
                answer_f1=0.5,
                judge_score=None,
                latency_ms=100,
            ),
            SimpleNamespace(
                retrieval_hit=None,
                reciprocal_rank=None,
                citation_hit=None,
                answer_f1=0.3,
                judge_score=None,
                latency_ms=300,
            ),
        ]
        summary = summarize(results)
        assert summary["hit_rate"] == 1.0
        assert summary["answer_f1"] == 0.4
        assert summary["judge_score"] is None
        assert summary["avg_latency_ms"] == 200


class TestJudgeParsing:
    def test_reads_json_even_with_text_around_it(self):
        assert parse_judge('Claro! {"score": 0.5, "reason": "incompleta"}') == (0.5, "incompleta")

    def test_clamps_score_to_zero_one(self):
        assert parse_judge('{"score": 3}')[0] == 1.0

    def test_unparseable_output_has_no_score(self):
        assert parse_judge("nota oito")[0] is None
