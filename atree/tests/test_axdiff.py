"""Phase 1 exit check: identity-keyed diffs beat the legacy implementation
by >=5x on bloated pairs, and the token table prints on every run."""
import json

from core import axdiff
from legacy_state_diff import generate_git_diff as legacy_diff

# Pairs where the legacy diff was bloated by ref/bounds churn must shrink 5x.
# Pairs that were already small only need to not regress.
BLOAT_THRESHOLD_TOK = 2000
REQUIRED_GAIN = 5.0


def test_token_reduction_vs_legacy(fixture_pairs):
    print("\n--- token table (chars/4) ---")
    print(f"{'pair':20} {'full':>8} {'legacy':>8} {'axdiff':>8} {'gain':>7}")
    for name, prev, curr in fixture_pairs:
        full = axdiff.estimate_tokens(json.dumps(curr, indent=2))
        legacy = axdiff.estimate_tokens(legacy_diff(prev, curr, strip_ephemeral=True))
        new = axdiff.diff(prev, curr).tokens
        gain = legacy / max(new, 1)
        print(f"{name:20} {full:>8,} {legacy:>8,} {new:>8,} {gain:>6.1f}x")

        assert new < legacy, f"{name}: no improvement over legacy"
        assert new < full, f"{name}: diff larger than the snapshot it replaces"
        if legacy >= BLOAT_THRESHOLD_TOK:
            assert gain >= REQUIRED_GAIN, (
                f"{name}: only {gain:.1f}x over legacy (need >={REQUIRED_GAIN}x) — "
                "ephemeral churn is leaking back into the diff"
            )


def test_identical_states_diff_empty(fixture_pairs):
    _, tree, _ = fixture_pairs[0]
    result = axdiff.diff(tree, tree)
    assert result.is_empty
    assert result.changed == 0


def test_ref_churn_alone_is_invisible(fixture_pairs):
    """The core fix: reassigning every ref_id must produce an EMPTY diff."""
    _, tree, _ = fixture_pairs[0]
    mutated = json.loads(json.dumps(tree))
    counter = [1000]

    def bump(node):
        if isinstance(node, dict):
            if "ref_id" in node:
                counter[0] += 1
                node["ref_id"] = f"@sNEW:e{counter[0]}"
            if "bounds" in node and isinstance(node["bounds"], dict):
                node["bounds"] = {k: v + 0.5 for k, v in node["bounds"].items()}
            for c in node.get("children", []):
                bump(c)

    bump(mutated)
    assert axdiff.diff(tree, mutated).is_empty, (
        "ref_id/bounds churn produced diff lines — the old bug is back"
    )


def test_real_change_is_visible(fixture_pairs):
    """A renamed button must appear in the diff even with zero ref churn."""
    _, tree, _ = fixture_pairs[0]
    mutated = json.loads(json.dumps(tree))
    renamed = [False]

    def rename_first_button(node):
        if renamed[0] or not isinstance(node, dict):
            return
        if node.get("role") == "button" and node.get("name"):
            node["name"] = node["name"] + " RENAMED"
            renamed[0] = True
            return
        for c in node.get("children", []):
            rename_first_button(c)

    rename_first_button(mutated)
    assert renamed[0], "fixture has no named button to rename"
    result = axdiff.diff(tree, mutated)
    assert not result.is_empty
    assert "RENAMED" in result.text


def test_sidecar_resolves_paths(fixture_pairs):
    _, _, curr = fixture_pairs[0]
    result = axdiff.diff({}, curr)
    content, sidecar = axdiff.flatten(curr)
    with_refs = [p for p, s in sidecar.items() if s.get("ref_id")]
    assert with_refs, "fixture exposes no ref_ids at all"
    hit = axdiff.resolve(with_refs[0], result.sidecar)
    assert hit is not None and hit["ref_id"], "sidecar lost the live ref"


def test_envelope_and_raw_tree_both_accepted(fixture_pairs):
    _, tree, _ = fixture_pairs[0]
    wrapped = {"ok": True, "data": {"tree": tree, "snapshot_id": "s1"}}
    assert axdiff.diff(wrapped, tree).is_empty
