"""litscan package.

Author: Ron Webb
Since: 1.0.0
"""

from env_dir_bootstrap import EnvDirBootstrap

__version__ = "1.3.1"

_bootstrapper = EnvDirBootstrap(
    env_var="LITSCAN_CONFIG_DIR",
    resources=["logging.ini", "lit_ignore"],
    package="litscan",
)

_bootstrapper.setup()

CONF_DIR = str(_bootstrapper.get_dir())
LIT_IGNORE_PATH = _bootstrapper.resolve("lit_ignore")
