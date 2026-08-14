#!/usr/bin/env sh

set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
source_dir="$project_root/app/web"
output_dir="$project_root/dist"
api_base=${FIRSTROLL_API_BASE:-}

case "$api_base" in
  https://*) ;;
  *)
    echo "FIRSTROLL_API_BASE must be the backend's https:// URL." >&2
    exit 1
    ;;
esac

rm -rf "$output_dir"
mkdir -p "$output_dir/assets"

cp "$source_dir/index.html" "$output_dir/index.html"
cp "$source_dir/app.js" "$output_dir/assets/app.js"
cp "$source_dir/closet3d.js" "$output_dir/assets/closet3d.js"
cp "$source_dir/favicon.svg" "$output_dir/assets/favicon.svg"
cp "$source_dir/styles.css" "$output_dir/assets/styles.css"
cp -R "$source_dir/models" "$output_dir/assets/models"
cp -R "$source_dir/vendor" "$output_dir/assets/vendor"

cat > "$output_dir/assets/config.js" <<EOF
window.FIRSTROLL_CONFIG = Object.freeze({
  apiBase: "${api_base}",
  publicMode: true,
  videoAnalysisEnabled: false,
});
EOF

echo "Built FirstRoll static site in $output_dir"
