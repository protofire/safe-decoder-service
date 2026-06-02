"""
Seismic SRC-20 ABIs.

SRC-20 is the Seismic chain's shielded variant of ERC-20. The transfer amount is
a `suint256` (shielded uint256): its value is encrypted on-chain. The selector is
computed exactly like any other function (``keccak256("transfer(address,suint256)")[:4]``
= ``0xb10c99b5``) treating ``suint256`` as a literal type string.

``suint256`` is NOT a canonical ABI type, so standard ABI codecs cannot (and must
not) decode the amount word into a plaintext number. The decoder special-cases
shielded types so the recipient ``address`` decodes normally while the shielded
amount is never surfaced as a plaintext value. See
``app.services.data_decoder.SHIELDED_ABI_TYPES``.
"""

src20_abi = [
    {
        "constant": False,
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "suint256", "name": "value", "type": "suint256"},
        ],
        "name": "transfer",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
]
