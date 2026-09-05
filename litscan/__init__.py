"""litscan package.

Author: Ron Webb
Since: 1.0.0
"""

from env_dir_bootstrap import EnvDirBootstrap

__version__ = "2.1.0"
__app_name__ = "litscan"

_bootstrapper = EnvDirBootstrap(
    env_var="LITSCAN_CONFIG_DIR",
    resources=["logging.ini", "lit_ignore", ".litscanignore"],
    package="litscan",
)

_bootstrapper.setup()

CONF_DIR = str(_bootstrapper.get_dir())
LIT_IGNORE_PATH = _bootstrapper.resolve("lit_ignore")
PATH_IGNORE_PATH = _bootstrapper.resolve(".litscanignore")
