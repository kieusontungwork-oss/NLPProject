"""Unit tests for board.py pure logic — no network, no gh."""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import board


def project_node(fields=None, items=None):
    return {
        "id": "P1",
        "number": 7,
        "title": "Delivery Board",
        "fields": {"nodes": fields or []},
        "items": {"nodes": items or []},
    }


STATUS_FIELD = {
    "id": "F-status",
    "name": "Status",
    "options": [{"id": "O-todo", "name": "Todo"},
                {"id": "O-review", "name": "In Review"}],
}
EPIC_FIELD = {
    "id": "F-epic",
    "name": "Epic",
    "options": [{"id": "O-e1", "name": "Epic 1"}],
}


class FindProjectTest(unittest.TestCase):
    def setUp(self):
        self.data = {"user": {"projectsV2": {"nodes": [
            project_node(), dict(project_node(), number=3, title="Other"),
        ]}}}

    def test_find_by_number(self):
        node = board.find_project(self.data, "user", 3)
        self.assertEqual(node["title"], "Other")

    def test_find_by_title_case_insensitive(self):
        node = board.find_project(self.data, "user", "delivery board")
        self.assertEqual(node["number"], 7)

    def test_missing_raises_when_required(self):
        with self.assertRaises(board.BoardError):
            board.find_project(self.data, "user", "Nope")

    def test_missing_returns_none_when_optional(self):
        self.assertIsNone(board.find_project(self.data, "user", "Nope",
                                             required=False))


class SingleSelectsTest(unittest.TestCase):
    def test_maps_only_single_select_fields(self):
        plain = {"id": "F-text", "name": "Notes"}
        fields = board.single_selects(project_node([plain, STATUS_FIELD]))
        self.assertEqual(set(fields), {"Status"})
        self.assertEqual(fields["Status"]["options"]["Todo"], "O-todo")


class ItemForIssueTest(unittest.TestCase):
    def test_finds_issue_item(self):
        items = [{"id": "I1", "content": {"number": 12, "title": "t"}}]
        node = board.item_for_issue(project_node(items=items), 12)
        self.assertEqual(node["id"], "I1")

    def test_missing_issue_raises(self):
        with self.assertRaises(board.BoardError):
            board.item_for_issue(project_node(), 99)


class ProjectItemsDataTest(unittest.TestCase):
    def test_flattens_field_values(self):
        items = [{
            "id": "I1",
            "fieldValues": {"nodes": [
                {"name": "In Review",
                 "field": {"name": "Status"}},
                {"text": "free text", "field": {"name": "Notes"}},
                {"name": "orphan"},  # no field name: dropped
            ]},
            "content": {"number": 5, "title": "t", "state": "OPEN",
                        "url": "u"},
        }]
        data = board.project_items_data(project_node(items=items))
        self.assertEqual(data[0]["fields"],
                         {"Status": "In Review", "Notes": "free text"})
        self.assertEqual(data[0]["issue"]["number"], 5)


class OptionIdForTest(unittest.TestCase):
    def setUp(self):
        self.fields = board.single_selects(
            project_node([STATUS_FIELD, EPIC_FIELD])
        )

    def test_existing_option(self):
        self.assertEqual(
            board.option_id_for(self.fields, "Status", "Todo", False),
            "O-todo",
        )

    def test_unknown_status_never_auto_creates(self):
        with self.assertRaises(board.BoardError):
            board.option_id_for(self.fields, "Status", "Done", False)

    def test_epic_option_auto_creates(self):
        with patch.object(board, "gh_graphql") as gql:
            gql.return_value = {"addProjectV2FieldOption": {
                "projectV2Field": {"id": "F-epic", "name": "Epic",
                                   "options": [{"id": "O-e1", "name": "Epic 1"},
                                               {"id": "O-e2", "name": "Epic 2"}]}}}
            self.assertEqual(
                board.option_id_for(self.fields, "Epic", "Epic 2", True),
                "O-e2",
            )
            self.assertIn("Epic 2", self.fields["Epic"]["options"])

    def test_missing_field_raises(self):
        with self.assertRaises(board.BoardError):
            board.option_id_for(self.fields, "Sprint", "S1", True)


class ResolveOwnerTest(unittest.TestCase):
    def test_user_owner(self):
        with patch.object(board, "gh_rest") as rest:
            rest.return_value = {"owner": {"login": "kim", "type": "User"}}
            self.assertEqual(board.resolve_owner("kim/repo"), ("kim", "user"))

    def test_org_owner(self):
        with patch.object(board, "gh_rest") as rest:
            rest.return_value = {"owner": {"login": "acme", "type": "Organization"}}
            self.assertEqual(board.resolve_owner("acme/repo"),
                             ("acme", "organization"))

    def test_unsupported_owner(self):
        with patch.object(board, "gh_rest") as rest:
            rest.return_value = {"owner": {"login": "x", "type": "Alien"}}
            with self.assertRaises(board.BoardError):
                board.resolve_owner("x/repo")


class CliTest(unittest.TestCase):
    def test_set_field_requires_a_field(self):
        with patch.object(board, "load_project") as load:
            load.return_value = ("kim", "user", project_node([STATUS_FIELD]))
            code = board.main(["set-field", "--repo", "kim/r",
                               "--project", "Delivery Board", "--issue", "1"])
            self.assertEqual(code, 1)

    def test_help_exits_cleanly(self):
        with self.assertRaises(SystemExit) as ctx:
            board.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
