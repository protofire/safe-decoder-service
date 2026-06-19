from app.commands.styles import print_command_title
from app.services.seismic_contracts_service import (
    update_seismic_contracts_info,
)


async def setup_seismic_contracts():
    print_command_title("Configuring Seismic SRC-20 contracts metadata")
    await update_seismic_contracts_info()
