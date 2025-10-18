import argparse
import logging
from app.core.logging_setup import setup_logging
from app.core.model_prefetch import prefetch_model
from app.core.models import resolve_repo_id
from app.diagnostics.runtime_info import dump_runtime_info


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="small")
    args = parser.parse_args()

    setup_logging(True)
    dump_runtime_info()

    repo_id = resolve_repo_id(args.model)
    local_path = prefetch_model(repo_id)
    logging.getLogger(__name__).info("Diagnostics complete. Model cached at %s", local_path)


if __name__ == "__main__":
    main()
