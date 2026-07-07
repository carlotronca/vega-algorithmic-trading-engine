from exchange.bitvavo_raw_rest import BitvavoRawREST


client = BitvavoRawREST()


print("")
print("=" * 80)
print("TEST RAW REST AUTH")
print("=" * 80)

response = client.get_balance()

print("")
print("=" * 80)
print("FINAL STATUS")
print(response.status_code)
print("=" * 80)
