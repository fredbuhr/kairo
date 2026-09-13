"""Initialize the private OpenBao target without printing recovery material."""

import argparse
import json
import os
import re
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = Path()
RECOVERY_FILE = Path()
WORKLOAD_META = Path()
BASE = []


def compose(args, *, stdin=None, allowed=(0,)):
    result = subprocess.run(
        [*BASE, *args], cwd=ROOT, input=stdin, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode not in allowed:
        raise RuntimeError(f"commande OpenBao refusee (code {result.returncode})")
    return result


def bao_as(token_file, args, *, stdin=None, allowed=(0,)):
    shell = 'export BAO_TOKEN="$(cat "$1")"; shift; exec bao "$@"'
    return compose(
        ["exec", "-T", "openbao", "sh", "-ec", shell,
         "sh", token_file, *args],
        stdin=stdin, allowed=allowed,
    )


def atomic_private_write(path, text):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chown(path, 0, 0)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def replace_env_token(token):
    lines = ENV_FILE.read_text().splitlines()
    found = 0
    output = []
    for line in lines:
        if line.startswith("OPENBAO_TOKEN="):
            line = "OPENBAO_TOKEN=" + token
            found += 1
        output.append(line)
    if found != 1:
        raise RuntimeError("OPENBAO_TOKEN absent ou duplique dans production.env")
    atomic_private_write(ENV_FILE, "\n".join(output) + "\n")


def env_token():
    matches = [
        line.split("=", 1)[1]
        for line in ENV_FILE.read_text().splitlines()
        if line.startswith("OPENBAO_TOKEN=")
    ]
    if len(matches) != 1:
        raise RuntimeError("OPENBAO_TOKEN absent ou duplique dans production.env")
    return matches[0]


def recovery_material():
    metadata = RECOVERY_FILE.stat()
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise RuntimeError("le fichier de recuperation doit appartenir a root en mode 0600")
    initialized = json.loads(RECOVERY_FILE.read_text())
    keys = initialized.get("unseal_keys_b64") or initialized.get("keys_base64")
    root_token = initialized.get("root_token")
    if not isinstance(keys, list) or len(keys) != 3 or not root_token:
        raise RuntimeError("reponse d'initialisation OpenBao inattendue")
    return keys, root_token


def accessor_keys(listing):
    if isinstance(listing, list):
        accessors = listing
    elif isinstance(listing, dict):
        data = listing.get("data")
        if not isinstance(data, dict) or "keys" not in data:
            raise RuntimeError("liste des accessors OpenBao inattendue")
        accessors = data["keys"]
    else:
        raise RuntimeError("liste des accessors OpenBao inattendue")
    if (not isinstance(accessors, list)
            or not all(isinstance(value, str) and value for value in accessors)):
        raise RuntimeError("liste des accessors OpenBao inattendue")
    return accessors


def revoke_interrupted_tokens():
    listing = json.loads(bao_as("/tmp/nevolium-root-token", [
        "list", "-format=json", "auth/token/accessors"
    ]).stdout)
    matches = []
    for accessor in accessor_keys(listing):
        lookup = json.loads(bao_as("/tmp/nevolium-root-token", [
            "write", "-format=json", "auth/token/lookup-accessor", "-"
        ], stdin=json.dumps({"accessor": accessor})).stdout).get("data", {})
        if (lookup.get("policies") == ["nevolium-core"]
                and int(lookup.get("period") or 0) == 604800):
            matches.append(accessor)
    if len(matches) != 1:
        raise RuntimeError(
            "la reprise attend exactement un jeton interrompu ; "
            f"{len(matches)} trouve"
        )
    bao_as("/tmp/nevolium-root-token", [
        "write", "-format=json", "auth/token/revoke-accessor", "-"
    ], stdin=json.dumps({"accessor": matches[0]}))
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--recovery-file", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    global ENV_FILE, RECOVERY_FILE, WORKLOAD_META, BASE
    ENV_FILE = args.env_file.absolute()
    RECOVERY_FILE = args.recovery_file.absolute()
    WORKLOAD_META = RECOVERY_FILE.with_name("openbao-workload.json")
    BASE = [
        "docker", "compose", "--env-file", str(ENV_FILE),
        "-f", "compose.yaml", "-f", "compose.production.yaml",
    ]

    if os.geteuid() != 0:
        raise SystemExit("ARRET : cette procedure doit etre executee avec sudo.")
    if (not ENV_FILE.is_file() or ENV_FILE.is_symlink()
            or ENV_FILE.parent.is_symlink()):
        raise SystemExit("ARRET : fichier d'environnement prive absent ou invalide.")
    if RECOVERY_FILE.parent.is_symlink():
        raise SystemExit("ARRET : repertoire de recuperation invalide.")
    if WORKLOAD_META.exists() or WORKLOAD_META.is_symlink():
        raise SystemExit("ARRET : les metadonnees du jeton existent deja.")

    init_status = compose(
        ["exec", "-T", "openbao", "bao", "operator", "init", "-status"],
        allowed=(0, 2),
    )
    if args.resume:
        if (not RECOVERY_FILE.is_file() or RECOVERY_FILE.is_symlink()
                or init_status.returncode != 0):
            raise SystemExit("ARRET : reprise incompatible avec l'etat OpenBao.")
        if "change_me" not in env_token().lower():
            raise SystemExit("ARRET : production.env contient deja un jeton OpenBao.")
        keys, root_token = recovery_material()
    else:
        if RECOVERY_FILE.exists() or RECOVERY_FILE.is_symlink():
            raise SystemExit("ARRET : le fichier de recuperation existe deja.")
        if init_status.returncode == 0:
            raise SystemExit("ARRET : OpenBao est deja initialise.")
        raw_initialization = compose([
            "exec", "-T", "openbao", "bao", "operator", "init",
            "-key-shares=3", "-key-threshold=2", "-format=json",
        ]).stdout
        atomic_private_write(RECOVERY_FILE, raw_initialization)
        keys, root_token = recovery_material()

    status = json.loads(compose(
        ["exec", "-T", "openbao", "bao", "status", "-format=json"],
        allowed=(0, 2),
    ).stdout)
    if status.get("sealed"):
        for key in keys[:2]:
            compose(
                ["exec", "-T", "openbao", "bao", "write", "-format=json",
                 "sys/unseal", "key=-"],
                stdin=key + "\n",
            )
        status = json.loads(compose(
            ["exec", "-T", "openbao", "bao", "status", "-format=json"]
        ).stdout)
    if status.get("sealed") or not status.get("initialized"):
        raise RuntimeError("OpenBao n'est pas correctement initialise et descelle")

    compose(
        ["exec", "-T", "openbao", "sh", "-ec",
         "umask 077; cat > /tmp/nevolium-root-token"],
        stdin=root_token + "\n",
    )

    workload_token = None
    try:
        policy = (ROOT / "infrastructure/openbao/policies/nevolium-core-read.hcl").read_text()
        bao_as("/tmp/nevolium-root-token", [
            "write", "-format=json", "sys/policies/acl/nevolium-core", "-"
        ], stdin=json.dumps({"policy": policy}))
        mounts = json.loads(bao_as("/tmp/nevolium-root-token", [
            "secrets", "list", "-format=json"
        ]).stdout)
        if "secret/" not in mounts:
            bao_as("/tmp/nevolium-root-token", [
                "write", "-format=json", "sys/mounts/secret", "-"
            ], stdin=json.dumps({"type": "kv", "options": {"version": "2"}}))
        elif (mounts["secret/"].get("type") != "kv"
              or mounts["secret/"].get("options", {}).get("version") != "2"):
            raise RuntimeError("le moteur secret/ existant n'est pas KV v2")

        revoked = revoke_interrupted_tokens() if args.resume else 0

        created = json.loads(bao_as("/tmp/nevolium-root-token", [
            "write", "-format=json", "auth/token/create", "-"
        ], stdin=json.dumps({
            "policies": ["nevolium-core"],
            "no_default_policy": True,
            "no_parent": True,
            "period": "168h",
            "display_name": "nevolium-core",
        })).stdout)
        workload_token = created["auth"]["client_token"]
        accessor = created["auth"]["accessor"]
        if not re.fullmatch(r"s\.[A-Za-z0-9]{24,}", workload_token):
            raise RuntimeError("jeton de workload OpenBao inattendu")

        compose(
            ["exec", "-T", "openbao", "sh", "-ec",
             "umask 077; cat > /tmp/nevolium-workload-token"],
            stdin=workload_token + "\n",
        )

        expected_capabilities = {
            "secret/data/nevolium/bootstrap-policy-check": {"read"},
            "auth/token/lookup-self": {"read"},
            "auth/token/renew-self": {"update"},
            "secret/data/outside-nevolium": {"deny"},
            "secret/metadata/nevolium": {"deny"},
            "sys/policies/acl/forbidden": {"deny"},
        }
        for path, expected in expected_capabilities.items():
            try:
                result = bao_as("/tmp/nevolium-workload-token", [
                    "token", "capabilities", path
                ])
            except RuntimeError as exc:
                raise RuntimeError(
                    f"verification de capability OpenBao pour {path}: {exc}"
                ) from None
            actual = set(result.stdout.split())
            if actual != expected:
                raise RuntimeError("capabilities workload OpenBao inattendues")

        renewed = json.loads(bao_as("/tmp/nevolium-workload-token", [
            "token", "renew", "-format=json"
        ]).stdout)
        if not renewed.get("auth", {}).get("renewable"):
            raise RuntimeError("le jeton de workload n'est pas renouvelable")

        replace_env_token(workload_token)
        atomic_private_write(WORKLOAD_META, json.dumps({
            "accessor": accessor,
            "display_name": "nevolium-core",
            "period_seconds": 604800,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }, indent=2, sort_keys=True) + "\n")
    finally:
        compose([
            "exec", "-T", "openbao", "sh", "-ec",
            "rm -f /tmp/nevolium-root-token /tmp/nevolium-workload-token",
        ], allowed=(0, 1))

    print("OpenBao initialise et descelle : 3 parts, seuil 2.")
    if args.resume:
        print(f"Reprise controlee : {revoked} jeton interrompu revoque.")
    print("Policy de lecture et quatre refus verifies.")
    print("Jeton periodique de 7 jours cree, renouvele et enregistre sans affichage.")
    print("Materiel de recuperation root:root 600 cree dans /etc/nevolium.")
    print("Aucun autre service Nevolium demarre.")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ARRET : {exc}") from None
