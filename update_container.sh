#!/bin/bash

if [ -f env/.env.prod ]; then
    source env/.env.prod
    echo "Loaded .env file"
else
    echo "файл env/.env.prod не найден"
    exit 1
fi

get_latest_tag() {
    if command -v gh &> /dev/null; then
        tag=$(gh release view -R "$BASE_REPO_NAME" --json tagName --jq '.tagName' 2>/dev/null)
        [ -n "$tag" ] && echo "$tag" && return 0
    fi

    if command -v jq &> /dev/null; then
        tag=$(curl -s "https://api.github.com/repos/$BASE_REPO_NAME/tags" | jq -r '.[0].name' 2>/dev/null)
        [ -n "$tag" ] && echo "$tag" && return 0
    fi

    if command -v python3 &> /dev/null; then
        tag=$(curl -s "https://api.github.com/repos/$BASE_REPO_NAME/tags" | \
              python3 -c "import json, sys; print(json.load(sys.stdin)[0]['name'])" 2>/dev/null)
        [ -n "$tag" ] && echo "$tag" && return 0
    fi

    echo "Error: Could not retrieve latest tag from $BASE_REPO_NAME" >&2
    return 1
}


if [ -z "$LATEST_TAG" ]; then
    LATEST_TAG=$(get_latest_tag)
fi

if [ -z "$LATEST_TAG" ]; then
    echo "Error: Could not get latest tag for $REPO_NAME"
    exit 1
fi

echo "$BASE_REPO_NAME tag: $LATEST_TAG"

rm -rf "$CLONE_DIR"
git clone "$DOCKER_REPO_URL" "$CLONE_DIR" 2> /dev/null
cd "$CLONE_DIR" || {
    echo "Error: Cannot enter directory $CLONE_DIR"
    exit 1
}

CURRENT_TAG=$(grep -E '^[[:space:]]*TAG=' Dockerfile | sed -E 's/^[[:space:]]*TAG=[\"'"'"']?([^\"'"'"']*)[\"'"'"']?/\1/' | head -1)

echo "Current tag in Dockerfile: $CURRENT_TAG"

if [ "$CURRENT_TAG" = "$LATEST_TAG" ]; then
    echo "Version is already up to date ($LATEST_TAG). No changes needed."
    cd ..
    curl -X POST ${PORTAINER_WEBHOOK_URL}
    rm -rf "$CLONE_DIR"
    exit 0
fi

echo "Version update required: $CURRENT_TAG -> $LATEST_TAG"

echo "Updating TAG in Dockerfile to: $LATEST_TAG"
if sed -i.bak -E "s|(TAG=)[\"'][^\"']*[\"']|\1\"$LATEST_TAG\"|g" Dockerfile; then
    echo "Successfully updated Dockerfile"
    rm -f Dockerfile.bak
else
    echo "Error: Failed to update Dockerfile. Trying alternative method..."
    if sed -i.bak -E "s|^(.*TAG=)(\"|')[^\"']*(\"|')(.*)$|\1\"$LATEST_TAG\"\4|g" Dockerfile; then
        echo "Successfully updated Dockerfile with alternative method"
        rm -f Dockerfile.bak
    else
        echo "Error: All update methods failed"
        exit 1
    fi
fi

if grep -q "TAG=\"$LATEST_TAG\"" Dockerfile; then
    echo "Verification: TAG successfully updated to $LATEST_TAG"
else
    echo "Error: TAG was not updated correctly"
    exit 1
fi

git add Dockerfile
git commit -m "version bumped up to $LATEST_TAG"
git push origin ${DOCKER_BRANCH_NAME}

cd ..
rm -rf "$CLONE_DIR"
curl -X POST ${PORTAINER_WEBHOOK_URL}

echo "Success! Version updated from $CURRENT_TAG to $LATEST_TAG"
