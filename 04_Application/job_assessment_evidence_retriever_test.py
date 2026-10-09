from career_evidence_catalog_builder import (
    load_saved_career_evidence_catalog,
)

from job_assessment_evidence_retriever import (
    retrieve_for_targets,
)

from job_assessment_schema import (
    AssessmentTarget,
)


TEST_TARGETS = [
    AssessmentTarget(
        target_id="REQ-001",
        target_type="required",
        text=(
            "Experience with "
            "Python scripting"
        ),
    ),
    AssessmentTarget(
        target_id="REQ-002",
        target_type="required",
        text=(
            "Experience with REST APIs"
        ),
    ),
    AssessmentTarget(
        target_id="PREF-001",
        target_type="preferred",
        text="Knowledge of Git",
    ),
    AssessmentTarget(
        target_id="EDU-001",
        target_type="education",
        text=(
            "Diploma or degree "
            "in engineering"
        ),
    ),
]


def main() -> None:
    print()
    print(
        "Job Assessment Evidence "
        "Retriever Test"
    )
    print(
        "============================="
    )
    print()

    catalog = (
        load_saved_career_evidence_catalog()
    )

    print(
        f"Loaded evidence items: "
        f"{len(catalog.evidence_items)}"
    )

    if not catalog.evidence_items:
        raise AssertionError(
            "Career evidence catalog is empty."
        )

    bundles = retrieve_for_targets(
        targets=TEST_TARGETS,
        catalog=catalog,
        top_k=5,
    )

    if (
        len(bundles)
        != len(TEST_TARGETS)
    ):
        raise AssertionError(
            "Target/bundle count "
            "mismatch."
        )

    for bundle in bundles:
        print()
        print(
            f"{bundle.target_id}: "
            f"{bundle.text}"
        )

        for candidate in (
            bundle.candidates
        ):
            print(
                f"  "
                f"{candidate.evidence_id} "
                f"[{candidate.source_type}] "
                f"score="
                f"{candidate.retrieval_score}"
            )

            print(
                f"    "
                f"{candidate.capability}"
            )

    python_bundle = (
        bundles[0]
    )

    if not (
        python_bundle.candidates
    ):
        raise AssertionError(
            "Python requirement returned "
            "no evidence candidates."
        )

    python_text = " ".join(
        (
            candidate.capability
            + " "
            + candidate.evidence_statement
        ).lower()
        for candidate in (
            python_bundle.candidates
        )
    )

    if "python" not in python_text:
        raise AssertionError(
            "Python evidence was not "
            "retrieved."
        )

    rest_bundle = (
        bundles[1]
    )

    if not (
        rest_bundle.candidates
    ):
        raise AssertionError(
            "REST API requirement returned "
            "no evidence candidates."
        )

    rest_text = " ".join(
        (
            candidate.capability
            + " "
            + candidate.evidence_statement
        ).lower()
        for candidate in (
            rest_bundle.candidates
        )
    )

    if (
        "rest api"
        not in rest_text
    ):
        raise AssertionError(
            "REST API evidence was not "
            "retrieved."
        )

    git_bundle = (
        bundles[2]
    )

    git_text = " ".join(
        (
            candidate.capability
            + " "
            + candidate.evidence_statement
        ).lower()
        for candidate in (
            git_bundle.candidates
        )
    )

    if "git" not in git_text:
        raise AssertionError(
            "Git evidence was not "
            "retrieved."
        )

    education_bundle = (
        bundles[3]
    )

    education_text = " ".join(
        (
            candidate.capability
            + " "
            + candidate.evidence_statement
            + " "
            + candidate.context
        ).lower()
        for candidate in (
            education_bundle.candidates
        )
    )

    if (
        "engineering"
        not in education_text
    ):
        raise AssertionError(
            "Engineering education "
            "evidence was not retrieved."
        )

    for bundle in bundles:
        if (
            len(bundle.candidates)
            > 5
        ):
            raise AssertionError(
                "Retriever exceeded "
                "top_k boundary."
            )

        candidate_ids = [
            candidate.evidence_id
            for candidate in (
                bundle.candidates
            )
        ]

        if (
            len(candidate_ids)
            != len(
                set(candidate_ids)
            )
        ):
            raise AssertionError(
                "Duplicate candidate IDs "
                f"for {bundle.target_id}."
            )

    print()
    print(
        "Frozen catalog load: PASS"
    )

    print(
        "Python retrieval: PASS"
    )

    print(
        "REST API retrieval: PASS"
    )

    print(
        "Git retrieval: PASS"
    )

    print(
        "Education retrieval: PASS"
    )

    print(
        "Bounded top-k retrieval: PASS"
    )

    print(
        "Unique candidates: PASS"
    )

    print()
    print(
        "Evidence Retrieval Layer: PASS"
    )


if __name__ == "__main__":
    main()