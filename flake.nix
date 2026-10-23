{
  description = "Pi-native development environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs = { self, nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          # Node's bundled npm lags the toolchain required by runtime delivery.
          # The registry tarball includes npm's dependencies; no install is needed.
          npm = pkgs.stdenvNoCC.mkDerivation rec {
            pname = "npm";
            version = "12.2.1";
            src = pkgs.fetchurl {
              url = "https://registry.npmjs.org/npm/-/npm-${version}.tgz";
              hash = "sha512-bKCmFRVT/BB+YPEYbZwQ1XUI3N5t4xKSpU1MxOjo7z3iWzKBJ0ZXRC1xFdEN+TC7N5TdywaBzf2dMXGJq/e2PQ==";
            };
            buildInputs = [ pkgs.nodejs_24 ];
            dontBuild = true;
            installPhase = ''
              runHook preInstall
              mkdir -p "$out/lib/node_modules/npm" "$out/bin"
              cp -R . "$out/lib/node_modules/npm/"
              ln -s ../lib/node_modules/npm/bin/npm-cli.js "$out/bin/npm"
              ln -s ../lib/node_modules/npm/bin/npx-cli.js "$out/bin/npx"
              runHook postInstall
            '';
          };
          # Keep Node/corepack, replacing the entire bundled npm output so old
          # files cannot leak into the new package. No Node rebuild is needed.
          nodejs = pkgs.nodejs_24.overrideAttrs (old: {
            paths = [ npm ] ++ builtins.filter (path: toString path != toString pkgs.nodejs-slim_24.npm) old.paths;
          });
        in
        {
          default = pkgs.mkShell {
            packages = with pkgs; [
              git
              gh
              ripgrep
              uv
              python3
              nodejs
            ];
          };
        });

      checks = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          manifest = builtins.fromJSON (builtins.readFile ./patches/pi-packages/langfuse-runtime/package.json);
          npmVersion = nixpkgs.lib.removePrefix "npm@" manifest.packageManager;
        in
        {
          npm-toolchain = pkgs.runCommand "check-npm-toolchain" {
            nativeBuildInputs = self.devShells.${system}.default.nativeBuildInputs;
          } ''
            node -e 'if (process.versions.node.split(".")[0] !== "24") process.exit(1)'
            test "$(npm --version)" = "${npmVersion}"
            test "$(npx --version)" = "${npmVersion}"
            # Delivery invokes node on the resolved npm CLI, not a shell wrapper.
            npm_cli=$(readlink -f "$(command -v npm)")
            test "$(node "$npm_cli" --version)" = "${npmVersion}"
            touch "$out"
          '';
        });
    };
}
