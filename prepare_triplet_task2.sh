#!/bin/bash

set -euo pipefail
IFS=$'\n\t'

# Arguments: paths to properties files for female, telco, business (in that order)
# If not provided, use default names in current directory
FEMALE_CELEBRITY_PROP=${1:-female_celebrity_properties.csv}
TELCO_PROP=${2:-telco_properties.csv}
BUSINESS_PROP=${3:-business_properties.csv}

# Check if files exist
if [ ! -f "$FEMALE_CELEBRITY_PROP" ]; then
    echo "Female Celebrity properties file not found: $FEMALE_CELEBRITY_PROP" >&2
    exit 1
fi
if [ ! -f "$TELCO_PROP" ]; then
    echo "Telco properties file not found: $TELCO_PROP" >&2
    exit 1
fi
if [ ! -f "$BUSINESS_PROP" ]; then
    echo "Business properties file not found: $BUSINESS_PROP" >&2
    exit 1
fi

# delete previous outputs
rm -rf "output/Corpus_Business_IRIT_ISWC-Train_Joint_(nous)_(without_Pertinence)_OK"
rm -rf "output/Female_Celebrity_FR (JointOnly-Thibault)"
rm -rf "output/Telco_V3_EN"
rm -f task2-train.zip task2-test.zip task2-groundtruth.zip

# regenerate outputs
uv run python -m triplet_task2.main -v "Female_Celebrity_FR (JointOnly-Thibault).json"
uv run python -m triplet_task2.main -v "Telco_V3_EN.json"
uv run python -m triplet_task2.main --no-split -v "Corpus_Business_IRIT_ISWC-Train_Joint_(nous)_(without_Pertinence)_OK.json"

# staging dirs
tmp_train_dir=$(mktemp -d)
tmp_test_dir=$(mktemp -d)
tmp_gt_dir=$(mktemp -d)
orig_pwd=$(pwd)

safe_copy() {
  src="$1"
  dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [ -f "$src" ]; then
    cp "$src" "$dst"
  else
    echo "Warning: missing $src" >&2
  fi
}

# female_celebrity
safe_copy "output/Female_Celebrity_FR (JointOnly-Thibault)/train/annotations.csv" "$tmp_train_dir/female_celebrity/annotations.csv"
safe_copy "output/Female_Celebrity_FR (JointOnly-Thibault)/train/documents.json" "$tmp_train_dir/female_celebrity/documents.json"
safe_copy "output/Female_Celebrity_FR (JointOnly-Thibault)/test/documents.json" "$tmp_test_dir/female_celebrity/documents.json"
safe_copy "output/Female_Celebrity_FR (JointOnly-Thibault)/test/annotations.csv" "$tmp_gt_dir/female_celebrity_groundtruth.csv"

# telco
safe_copy "output/Telco_V3_EN/train/annotations.csv" "$tmp_train_dir/telco/annotations.csv"
safe_copy "output/Telco_V3_EN/train/documents.json" "$tmp_train_dir/telco/documents.json"
safe_copy "output/Telco_V3_EN/test/documents.json" "$tmp_test_dir/telco/documents.json"
safe_copy "output/Telco_V3_EN/test/annotations.csv" "$tmp_gt_dir/telco_groundtruth.csv"

# business
safe_copy "output/Corpus_Business_IRIT_ISWC-Train_Joint_(nous)_(without_Pertinence)_OK/train/annotations.csv" "$tmp_train_dir/business/annotations.csv"
safe_copy "output/Corpus_Business_IRIT_ISWC-Train_Joint_(nous)_(without_Pertinence)_OK/train/documents.json" "$tmp_train_dir/business/documents.json"
safe_copy "output/Corpus_Business_IRIT_ISWC-Train_Joint_(nous)_(without_Pertinence)_OK/test/documents.json" "$tmp_test_dir/business/documents.json"
safe_copy "output/Corpus_Business_IRIT_ISWC-Train_Joint_(nous)_(without_Pertinence)_OK/test/annotations.csv" "$tmp_gt_dir/business_groundtruth.csv"

# copy properties files into test packages
safe_copy "$FEMALE_CELEBRITY_PROP" "$tmp_train_dir/female_celebrity/properties.csv"
safe_copy "$FEMALE_CELEBRITY_PROP" "$tmp_test_dir/female_celebrity/properties.csv"
safe_copy "$TELCO_PROP" "$tmp_train_dir/telco/properties.csv"
safe_copy "$TELCO_PROP" "$tmp_test_dir/telco/properties.csv"
safe_copy "$BUSINESS_PROP" "$tmp_train_dir/business/properties.csv"
safe_copy "$BUSINESS_PROP" "$tmp_test_dir/business/properties.csv"

# create zips
rm -f "$orig_pwd/task2-train.zip"
( cd "$tmp_train_dir" && zip -r -q "$orig_pwd/task2-train.zip" . )
rm -f "$orig_pwd/task2-test.zip"
( cd "$tmp_test_dir"  && zip -r -q "$orig_pwd/task2-test.zip"  . )
rm -f "$orig_pwd/task2-groundtruth.zip"
( cd "$tmp_gt_dir"    && zip -r -q "$orig_pwd/task2-groundtruth.zip" . )

# cleanup
rm -rf "$tmp_train_dir" "$tmp_test_dir" "$tmp_gt_dir"

echo "Created: task2-train.zip, task2-test.zip, task2-groundtruth.zip"