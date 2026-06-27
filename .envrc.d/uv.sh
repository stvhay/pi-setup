# Initialize a project-local Python environment with uv.
# The environment is intentionally local and ignored by git.

if has uv && [[ -f pyproject.toml ]]; then
  export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$PWD/.venv}"
  if [[ ! -d "$UV_PROJECT_ENVIRONMENT" ]]; then
    uv venv "$UV_PROJECT_ENVIRONMENT"
  fi
  PATH_add "$UV_PROJECT_ENVIRONMENT/bin"
fi
