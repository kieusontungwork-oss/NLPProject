#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""GitHub Projects v2 field and item operations, wrapped around the gh CLI.

Projects v2 mutations are verbose GraphQL and lose field/option IDs easily;
this script owns them so callers get stable JSON back. Auth and network are
handled entirely by `gh` — this script never talks to the API itself.

Subcommands:
  ensure     Find or create a project; ensure Status/Epic/Sprint single-select fields.
  add-item   Add an issue to a project, optionally setting fields.
  set-field  Set Status/Epic/Sprint on the project item for an issue.
  list       Dump project items with their field values as JSON.

Status values are fixed (Todo, In Progress, In Review, Done) and never
auto-created; Epic and Sprint options are created on demand.

Exit codes: 0 ok, 1 lookup/validation failure, 2 gh/API failure.
"""

import argparse
import json
import subprocess
import sys

STATUS_OPTIONS = ["Todo", "In Progress", "In Review", "Done"]

FIELDS_FRAGMENT = """fields(first: 50) { nodes {
  ... on ProjectV2SingleSelectField { id name options { id name } }
  ... on ProjectV2Field { id name }
  ... on ProjectV2IterationField { id name }
} }"""

PROJECTS_QUERY = """
query($login: String!) {
  %OWNER%(login: $login) {
    id
    projectsV2(first: 50) { nodes { id number title %FIELDS% } }
  }
}
"""

PROJECT_ITEMS_QUERY = """
query($login: String!, $number: Int!) {
  %OWNER%(login: $login) { projectV2(number: $number) {
    id title number
    items(first: 100) { nodes {
      id
      fieldValues(first: 20) { nodes {
        ... on ProjectV2ItemFieldSingleSelectValue { name
          field { ... on ProjectV2SingleSelectField { name } } }
        ... on ProjectV2ItemFieldTextValue { text
          field { ... on ProjectV2Field { name } } }
      } }
      content { ... on Issue { number title state url } }
    } }
  } }
}
"""

CREATE_PROJECT_MUTATION = """
mutation($ownerId: ID!, $title: String!) {
  createProjectV2(input: {ownerId: $ownerId, title: $title}) {
    projectV2 { id number title %FIELDS% }
  }
}
"""

CREATE_FIELD_MUTATION = """
mutation($projectId: ID!, $name: String!, $options: [ProjectV2SingleSelectFieldOptionInput!]) {
  createProjectV2Field(input: {projectId: $projectId, dataType: SINGLE_SELECT,
      name: $name, singleSelectOptions: $options}) {
    projectV2Field { ... on ProjectV2SingleSelectField { id name options { id name } } }
  }
}
"""

ADD_OPTION_MUTATION = """
mutation($fieldId: ID!, $name: String!) {
  addProjectV2FieldOption(input: {fieldId: $fieldId, name: $name}) {
    projectV2Field { ... on ProjectV2SingleSelectField { id name options { id name } } }
  }
}
"""

ADD_ITEM_MUTATION = """
mutation($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
    item { id }
  }
}
"""

SET_FIELD_MUTATION = """
mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
  updateProjectV2ItemFieldValue(input: {projectId: $projectId, itemId: $itemId,
      fieldId: $fieldId, value: {singleSelectOptionId: $optionId}}) {
    projectV2Item { id }
  }
}
"""


def filled(query, owner_field):
    """Fill the owner and fields placeholders into a query template."""
    return query.replace("%OWNER%", owner_field).replace("%FIELDS%", FIELDS_FRAGMENT)


class BoardError(Exception):
    """Lookup or validation failure (exit 1)."""


class GhError(Exception):
    """gh or API failure (exit 2)."""


def gh_graphql(query, variables, verbose=False):
    """Run one GraphQL call through gh and return the parsed data payload."""
    cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        if value is not None:
            cmd += ["-F", f"{key}={value}"]
    if verbose:
        print(f"gh: gh api graphql ({len(query)} chars)", file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise GhError(f"gh api graphql failed: {proc.stderr.strip()}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise GhError(f"gh returned unparsable JSON: {exc}") from exc
    if payload.get("errors"):
        raise GhError(f"GraphQL errors: {json.dumps(payload['errors'])}")
    return payload["data"]


def gh_rest(path, verbose=False):
    """Run one REST call through gh and return parsed JSON."""
    cmd = ["gh", "api", path]
    if verbose:
        print(f"gh: gh api {path}", file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise GhError(f"gh api {path} failed: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise GhError(f"gh returned unparsable JSON: {exc}") from exc


def resolve_owner(repo, verbose=False):
    """Resolve OWNER/REPO into (owner_login, graphql_owner_field)."""
    data = gh_rest(f"repos/{repo}", verbose=verbose)
    owner = data.get("owner") or {}
    owner_type = owner.get("type")
    if owner_type == "Organization":
        return owner["login"], "organization"
    if owner_type in ("User", "Bot"):
        return owner["login"], "user"
    raise BoardError(f"unsupported owner type {owner_type!r} for {repo!r}")


def find_project(data, owner_field, ref, required=True):
    """Find a project by number or title in an owner's project list."""
    nodes = data[owner_field]["projectsV2"]["nodes"]
    ref_str = str(ref)
    for node in nodes:
        if ref_str.isdigit() and node["number"] == int(ref_str):
            return node
        if node["title"].lower() == ref_str.lower():
            return node
    if not required:
        return None
    titles = [node["title"] for node in nodes]
    raise BoardError(f"project {ref!r} not found; existing projects: {titles}")


def single_selects(project_node):
    """Map field name -> {id, options: {name: id}} for single-select fields."""
    fields = {}
    for node in project_node["fields"]["nodes"]:
        if "options" in node:
            fields[node["name"]] = {
                "id": node["id"],
                "options": {opt["name"]: opt["id"] for opt in node["options"]},
            }
    return fields


def ensure_field(owner_field, project_node, name, options, verbose=False):
    """Create a single-select field when missing; return its {id, options}."""
    result = gh_graphql(
        CREATE_FIELD_MUTATION,
        {
            "projectId": project_node["id"],
            "name": name,
            "options": None if options is None
            else [{"name": opt} for opt in options],
        },
        verbose=verbose,
    )
    node = result["createProjectV2Field"]["projectV2Field"]
    print(f"created field {name!r} on project {project_node['title']!r}",
          file=sys.stderr)
    return {
        "id": node["id"],
        "options": {opt["name"]: opt["id"] for opt in node["options"]},
    }


def option_id_for(fields, field_name, value, auto_create, verbose=False):
    """Resolve a value to its option id, creating the option when allowed."""
    field = fields.get(field_name)
    if field is None:
        raise BoardError(f"field {field_name!r} does not exist on this project")
    if value in field["options"]:
        return field["options"][value]
    if not auto_create:
        raise BoardError(
            f"{value!r} is not a valid {field_name} option; "
            f"valid: {sorted(field['options'])}"
        )
    result = gh_graphql(
        ADD_OPTION_MUTATION,
        {"fieldId": field["id"], "name": value},
        verbose=verbose,
    )
    node = result["addProjectV2FieldOption"]["projectV2Field"]
    field["options"] = {opt["name"]: opt["id"] for opt in node["options"]}
    print(f"created option {value!r} on field {field_name!r}", file=sys.stderr)
    return field["options"][value]


def item_for_issue(project_node, issue_number):
    """Find the project item holding a given issue number."""
    for node in project_node["items"]["nodes"]:
        content = node.get("content") or {}
        if content.get("number") == issue_number:
            return node
    raise BoardError(
        f"issue #{issue_number} is not on project {project_node['title']!r}"
    )


def project_items_data(project_node):
    """Flatten project items into plain dicts with a field-value map."""
    items = []
    for node in project_node["items"]["nodes"]:
        values = {}
        for fv in node["fieldValues"]["nodes"]:
            field = fv.get("field") or {}
            name = field.get("name")
            if name:
                values[name] = fv.get("name") or fv.get("text")
        content = node.get("content") or {}
        items.append({
            "item_id": node["id"],
            "issue": {key: content[key]
                      for key in ("number", "title", "state", "url")
                      if key in content},
            "fields": values,
        })
    return items


def load_project(repo, project_ref, with_items=False, verbose=False):
    """Load a project node by title/number, optionally with its items."""
    owner, owner_field = resolve_owner(repo, verbose=verbose)
    data = gh_graphql(
        filled(PROJECTS_QUERY, owner_field), {"login": owner}, verbose=verbose
    )
    if project_ref is None:
        raise BoardError("a project reference is required")
    node = find_project(data, owner_field, project_ref)
    if with_items:
        data = gh_graphql(
            filled(PROJECT_ITEMS_QUERY, owner_field),
            {"login": owner, "number": node["number"]},
            verbose=verbose,
        )
        node = find_project(data, owner_field, node["number"])
    return owner, owner_field, node


def set_requested_fields(args, project_node, item_id):
    """Apply --status/--epic/--sprint options; error when none were given."""
    fields = single_selects(project_node)
    requests = [
        ("Status", args.status, False),
        ("Epic", args.epic, True),
        ("Sprint", args.sprint, True),
    ]
    given = [req for req in requests if req[1] is not None]
    if not given:
        raise BoardError("nothing to set: pass --status, --epic, and/or --sprint")
    for field_name, value, auto_create in given:
        option_id = option_id_for(fields, field_name, value, auto_create,
                                  verbose=args.verbose)
        gh_graphql(
            SET_FIELD_MUTATION,
            {
                "projectId": project_node["id"],
                "itemId": item_id,
                "fieldId": fields[field_name]["id"],
                "optionId": option_id,
            },
            verbose=args.verbose,
        )


def cmd_ensure(args):
    owner, owner_field = resolve_owner(args.repo, verbose=args.verbose)
    data = gh_graphql(
        filled(PROJECTS_QUERY, owner_field), {"login": owner}, verbose=args.verbose
    )
    node = find_project(data, owner_field, args.title, required=False)
    created = node is None
    if created:
        result = gh_graphql(
            filled(CREATE_PROJECT_MUTATION, owner_field),
            {"ownerId": data[owner_field]["id"], "title": args.title},
            verbose=args.verbose,
        )
        node = result["createProjectV2"]["projectV2"]
        print(f"created project {args.title!r}", file=sys.stderr)
    fields = single_selects(node)
    for name, options in (("Status", STATUS_OPTIONS), ("Epic", None),
                          ("Sprint", None)):
        if name not in fields:
            fields[name] = ensure_field(owner_field, node, name, options,
                                        verbose=args.verbose)
    return {
        "created": created,
        "project": {"id": node["id"], "number": node["number"],
                    "title": node["title"]},
        "fields": fields,
    }


def cmd_add_item(args):
    _, _, node = load_project(args.repo, args.project, verbose=args.verbose)
    issue = gh_rest(f"repos/{args.repo}/issues/{args.issue}",
                    verbose=args.verbose)
    if "pull_request" in issue:
        raise BoardError(f"#{args.issue} is a pull request, not an issue")
    result = gh_graphql(
        ADD_ITEM_MUTATION,
        {"projectId": node["id"], "contentId": issue["node_id"]},
        verbose=args.verbose,
    )
    item_id = result["addProjectV2ItemById"]["item"]["id"]
    print(f"added issue #{args.issue} as item {item_id}", file=sys.stderr)
    if args.status or args.epic or args.sprint:
        set_requested_fields(args, node, item_id)
    return {"item_id": item_id, "issue": args.issue, "project": node["title"]}


def cmd_set_field(args):
    _, _, node = load_project(args.repo, args.project, with_items=True,
                              verbose=args.verbose)
    item = item_for_issue(node, args.issue)
    set_requested_fields(args, node, item["id"])
    return {"item_id": item["id"], "issue": args.issue, "project": node["title"]}


def cmd_list(args):
    _, _, node = load_project(args.repo, args.project, with_items=True,
                              verbose=args.verbose)
    return {
        "project": {"number": node["number"], "title": node["title"]},
        "items": project_items_data(node),
    }


def build_parser():
    parser = argparse.ArgumentParser(
        prog="board.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--verbose", action="store_true",
                        help="log gh invocations to stderr")
    sub = parser.add_subparsers(dest="command", required=True)

    ensure = sub.add_parser("ensure", help="find or create project + fields")
    ensure.add_argument("--repo", required=True, help="OWNER/REPO")
    ensure.add_argument("--title", default="Delivery Board")
    ensure.set_defaults(func=cmd_ensure)

    add_item = sub.add_parser("add-item", help="add an issue to a project")
    add_item.add_argument("--repo", required=True, help="OWNER/REPO")
    add_item.add_argument("--project", required=True, help="title or number")
    add_item.add_argument("--issue", required=True, type=int)
    add_item.add_argument("--status")
    add_item.add_argument("--epic")
    add_item.add_argument("--sprint")
    add_item.set_defaults(func=cmd_add_item)

    set_field = sub.add_parser("set-field", help="set fields on an issue's item")
    set_field.add_argument("--repo", required=True, help="OWNER/REPO")
    set_field.add_argument("--project", required=True, help="title or number")
    set_field.add_argument("--issue", required=True, type=int)
    set_field.add_argument("--status")
    set_field.add_argument("--epic")
    set_field.add_argument("--sprint")
    set_field.set_defaults(func=cmd_set_field)

    list_cmd = sub.add_parser("list", help="dump items + field values")
    list_cmd.add_argument("--repo", required=True, help="OWNER/REPO")
    list_cmd.add_argument("--project", required=True, help="title or number")
    list_cmd.set_defaults(func=cmd_list)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except BoardError as exc:
        message = str(exc)
        print(json.dumps({"error": message}))
        print(f"error: {message}", file=sys.stderr)
        return 1
    except GhError as exc:
        message = str(exc)
        print(json.dumps({"error": message}))
        print(f"error: {message}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
