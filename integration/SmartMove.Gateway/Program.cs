using System.Net;

var builder = WebApplication.CreateBuilder(args);
var upstream = new Uri(builder.Configuration["SMARTMOVE_UPSTREAM"] ?? "http://127.0.0.1:8501");
if (!upstream.IsLoopback)
    throw new InvalidOperationException("This local gateway accepts a loopback upstream only.");
builder.WebHost.UseUrls(builder.Configuration["SMARTMOVE_GATEWAY_URL"] ?? "http://localhost:5080");
builder.Services.AddHttpClient("upstream").ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler
{
    AllowAutoRedirect = false,
    UseCookies = false,
    AutomaticDecompression = DecompressionMethods.None
});
var app = builder.Build();
var hopHeaders = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
{
    "Connection", "Keep-Alive", "Proxy-Authenticate", "Proxy-Authorization", "TE", "Trailer", "Transfer-Encoding", "Upgrade"
};
app.Run(async context =>
{
    var path = context.Request.Path.Value ?? "/";
    if (!(path == "/" || path == "/favicon.ico" || path.StartsWith("/api/", StringComparison.Ordinal) || path.StartsWith("/static/", StringComparison.Ordinal)))
    {
        context.Response.StatusCode = 404;
        return;
    }
    var target = new Uri(upstream, path + context.Request.QueryString);
    using var message = new HttpRequestMessage(new HttpMethod(context.Request.Method), target);
    if (context.Request.ContentLength > 0 || context.Request.Headers.ContainsKey("Transfer-Encoding"))
        message.Content = new StreamContent(context.Request.Body);
    foreach (var header in context.Request.Headers)
    {
        if (hopHeaders.Contains(header.Key) || header.Key.StartsWith("X-Forwarded-", StringComparison.OrdinalIgnoreCase))
            continue;
        if (!message.Headers.TryAddWithoutValidation(header.Key, header.Value.ToArray()) && message.Content is not null)
            message.Content.Headers.TryAddWithoutValidation(header.Key, header.Value.ToArray());
    }
    message.Headers.Host = context.Request.Host.Value;
    message.Headers.TryAddWithoutValidation("X-Forwarded-Proto", context.Request.Scheme);
    try
    {
        var client = context.RequestServices.GetRequiredService<IHttpClientFactory>().CreateClient("upstream");
        using var result = await client.SendAsync(message, HttpCompletionOption.ResponseHeadersRead, context.RequestAborted);
        context.Response.StatusCode = (int)result.StatusCode;
        foreach (var header in result.Headers.Concat(result.Content.Headers))
            if (!hopHeaders.Contains(header.Key))
                context.Response.Headers[header.Key] = header.Value.ToArray();
        await result.Content.CopyToAsync(context.Response.Body, context.RequestAborted);
    }
    catch (HttpRequestException)
    {
        context.Response.StatusCode = 502;
        await context.Response.WriteAsJsonAsync(new { detail = "SmartMove Python API is not running on the loopback upstream." });
    }
});
app.Run();
