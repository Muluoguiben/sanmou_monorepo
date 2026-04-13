from pathlib import Path
import unittest

from qa_agent.knowledge.models import Coverage
from qa_agent.knowledge.source_paths import discover_source_paths
from qa_agent.service.query_service import QueryService


class QueryServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project_root = Path(__file__).resolve().parents[1]
        source_paths = discover_source_paths(project_root / "knowledge_sources")
        cls.service = QueryService.from_source_paths(source_paths)

    def test_resolve_term_maps_alias_to_canonical_topic(self) -> None:
        response = self.service.resolve_term("补兵")
        self.assertEqual(response.coverage, Coverage.EXACT)
        self.assertEqual(response.evidence[0].topic, "征兵")
        self.assertEqual(response.evidence[0].entry_id, "team-recruit")

    def test_lookup_topic_prefers_domain_filtered_result(self) -> None:
        response = self.service.lookup_topic("章节", domain="chapter")
        self.assertEqual(response.coverage, Coverage.EXACT)
        self.assertEqual(response.evidence[0].domain.value, "chapter")
        self.assertEqual(response.evidence[0].topic, "章节任务")

    def test_answer_rule_question_returns_evidence(self) -> None:
        response = self.service.answer_rule_question("建筑升级需要满足什么条件？", domain="building")
        self.assertIn("资源充足", response.answer)
        self.assertEqual(response.evidence[0].entry_id, "building-upgrade")
        self.assertNotEqual(response.coverage, Coverage.NOT_FOUND)

    def test_not_found_question_does_not_fabricate(self) -> None:
        response = self.service.answer_rule_question("神器熔铸规则是什么？")
        self.assertEqual(response.coverage, Coverage.NOT_FOUND)
        self.assertEqual(response.evidence, [])
        self.assertIn("暂未收录", response.answer)

    def test_partial_match_returns_related_followups(self) -> None:
        response = self.service.lookup_topic("主线")
        self.assertEqual(response.coverage, Coverage.PARTIAL)
        self.assertIn("章节奖励", response.followups)

    def test_disambiguation_with_domain_avoids_cross_domain_hits(self) -> None:
        response = self.service.answer_rule_question("体力不足时怎么办？", domain="team")
        self.assertEqual(response.evidence[0].domain.value, "team")
        self.assertEqual(response.evidence[0].topic, "体力")

    def test_new_building_prerequisite_topic_is_queryable(self) -> None:
        response = self.service.lookup_topic("升级前置", domain="building")
        self.assertEqual(response.coverage, Coverage.EXACT)
        self.assertEqual(response.evidence[0].entry_id, "building-prerequisite")

    def test_new_combat_land_level_question_hits_land_level(self) -> None:
        response = self.service.answer_rule_question("几级地要怎么判断能不能打？", domain="combat")
        top_ids = {item.entry_id for item in response.evidence}
        self.assertTrue(
            {"mech-land-difficulty-factors", "combat-land-level"} & top_ids,
            f"expected difficulty/land-level entry in evidence, got {top_ids}",
        )

    def test_hero_schema_topic_is_queryable(self) -> None:
        response = self.service.lookup_topic("武将资料字段", domain="hero")
        self.assertEqual(response.coverage, Coverage.EXACT)
        self.assertEqual(response.evidence[0].entry_id, "hero-schema")

    def test_skill_schema_topic_is_queryable(self) -> None:
        response = self.service.answer_rule_question("批量录入战法至少要有哪些字段？", domain="skill")
        self.assertEqual(response.evidence[0].entry_id, "skill-schema")
        self.assertIn("至少应包含", response.answer)

    def test_status_registry_is_queryable(self) -> None:
        response = self.service.lookup_topic("状态注册表", domain="status")
        self.assertEqual(response.coverage, Coverage.EXACT)
        self.assertEqual(response.evidence[0].entry_id, "status-batch-registry")

    def test_lineup_registry_is_queryable(self) -> None:
        response = self.service.lookup_topic("阵容注册表", domain="solution")
        self.assertEqual(response.coverage, Coverage.EXACT)
        self.assertEqual(response.evidence[0].entry_id, "lineup-batch-registry")

    def test_status_profile_is_queryable(self) -> None:
        response = self.service.lookup_topic("震慑", domain="status")
        self.assertEqual(response.coverage, Coverage.EXACT)
        self.assertEqual(response.evidence[0].entry_id, "status-stun")
        self.assertIn("无法行动", response.answer)

    def test_status_group_question_hits_control_group(self) -> None:
        response = self.service.answer_rule_question("控制状态包括什么？", domain="status")
        self.assertEqual(response.evidence[0].entry_id, "status-control-group")
        self.assertIn("震慑", response.answer)

    def test_lineup_rating_taxonomy_is_queryable(self) -> None:
        response = self.service.lookup_topic("T0搭配", domain="solution")
        self.assertEqual(response.coverage, Coverage.EXACT)
        self.assertEqual(response.evidence[0].entry_id, "lineup-rating-taxonomy")

    def test_specific_hero_is_queryable(self) -> None:
        response = self.service.lookup_topic("诸葛亮", domain="hero")
        self.assertEqual(response.coverage, Coverage.EXACT)
        self.assertEqual(response.evidence[0].entry_id, "hero-zhugeliang")
        self.assertIn("蜀", response.answer)

    def test_specific_skill_is_queryable(self) -> None:
        response = self.service.lookup_topic("盛气凌敌", domain="skill")
        self.assertEqual(response.coverage, Coverage.EXACT)
        self.assertEqual(response.evidence[0].entry_id, "skill-shengqilingdi")
        self.assertIn("指挥", response.answer)

    def test_hero_alias_resolution_hits_canonical_topic(self) -> None:
        response = self.service.resolve_term("卧龙", domain="hero")
        self.assertEqual(response.coverage, Coverage.EXACT)
        self.assertEqual(response.evidence[0].topic, "诸葛亮")

    def test_skill_alias_resolution_hits_canonical_topic(self) -> None:
        response = self.service.resolve_term("盛气临敌", domain="skill")
        self.assertEqual(response.coverage, Coverage.EXACT)
        self.assertEqual(response.evidence[0].topic, "盛气凌敌")


if __name__ == "__main__":
    unittest.main()
