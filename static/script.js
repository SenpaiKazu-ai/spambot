async function sharePost() {
  const link = document.getElementById("linkToPost").value.trim();
  const tokensText = document.getElementById("accessTokens").value.trim();
  const count = parseInt(document.getElementById("shareCount").value);
  const result = document.getElementById("result");

  if (!link || !tokensText) {
    result.innerHTML = "⚠️ Please fill in the link and at least one access token.";
    return;
  }

  const tokens = tokensText
    .split("\n")
    .map(t => t.trim())
    .filter(t => t);

  result.innerHTML = `⏳ Sharing with ${tokens.length} token(s)...`;

  // Create an array of promises for all tokens
  const sharePromises = tokens.map(async token => {
    try {
      const res = await fetch("/api/share", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ link, accessToken: token, count })
      });

      const text = await res.text();
      const data = text.startsWith("<") ? {} : JSON.parse(text);

      if (data.results) {
        return data.results.filter(r => !r.error).length; // number of successful shares
      }
      return 0;
    } catch (err) {
      console.error(`Token failed: ${token}`, err);
      return 0;
    }
  });

  // Wait for all requests to finish
  const results = await Promise.all(sharePromises);
  const totalSuccess = results.reduce((a, b) => a + b, 0);

  result.innerHTML = `✅ Shared ${totalSuccess} posts successfully using ${tokens.length} token(s).`;
}
