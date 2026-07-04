"""litscan package.

Author: Ron Webb
Since: 1.0.0
"""

from env_dir_bootstrap import EnvDirBootstrap

__version__ = "1.4.0"
__app_name__ = "litscan"

_bootstrapper = EnvDirBootstrap(
    env_var="LITSCAN_CONFIG_DIR",
    resources=["logging.ini", "lit_ignore", "lit_brace_ext", "lit_control_kw"],
    package="litscan",
)

_bootstrapper.setup()

CONF_DIR = str(_bootstrapper.get_dir())
LIT_IGNORE_PATH = _bootstrapper.resolve("lit_ignore")
LIT_BRACE_EXT_PATH = _bootstrapper.resolve("lit_brace_ext")
LIT_CONTROL_KW_PATH = _bootstrapper.resolve("lit_control_kw")
