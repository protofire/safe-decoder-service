# MultiSendCallOnly on TRON Shasta, as returned by
# POST https://api.shasta.trongrid.io/wallet/getcontract {"value": "41f1dd46af04774c999e213fa6df2b4278bba8a757"}

mock_tron_abi_json: dict = {
    "entrys": [
        {
            "inputs": [{"name": "transactions", "type": "bytes"}],
            "name": "multiSend",
            "stateMutability": "Payable",
            "type": "Function",
        }
    ]
}
