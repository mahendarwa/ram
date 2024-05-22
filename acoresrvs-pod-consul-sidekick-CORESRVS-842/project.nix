{ config, lib, modulesPath, pkgs, ... }:

{
  require = [
    "${modulesPath}/tools/mod-lean-python.nix"
    "${modulesPath}/languages/python-poetry.nix"
    "${modulesPath}/builders/docker.nix"
  ];

  name = "pod-consul-sidekick";
  src = lib.sourceByRegex ./. [
    "^pod_consul_sidekick$"
    "^pod_consul_sidekick/.*"
    "^poetry\.lock$"
    "^pyproject\.toml$"
    "^README\.md"
  ];

  lean_python = {
    enable = true;
    package = pkgs.python311;
    configd = true;
    expat = true;
    libffi = true;
    openssl = true;
    zlib = true;
  };

  python = {
    enable = true;
    modules = {
      pod_consul_sidekick = ./pod_consul_sidekick;
    };
    package = config.out_lean_python;
    inject_app_env = true;
    prefer_wheels = false;
    overrides = self: super: {
      azure-mgmt-resourcegraph = super.azure-mgmt-resourcegraph.overridePythonAttrs (old: {
        nativeBuildInputs = old.nativeBuildInputs ++ [
          self.setuptools
        ];
      });

    };
  };

  docker = {
    enable = true;

    # layout of the root directory
    contents = [
      config.out_python
      pkgs.busybox # only for debugging
    ];

    command = [ "${config.out_python}/bin/pod-consul-sidekick" ];

    # getting permission error on some k8s clusters
    user = "65535:65535";
  };

  dev_commands = with pkgs; [
    awscli2
    azure-cli
  ];
}
