from pytest_httpx import HTTPXMock

response = {
    "id": "chatcmpl-8uq5isFy4wOx47MRGZIbz5qa23miM",
    "object": "chat.completion",
    "created": 1708557298,
    "model": "gpt-3.5-turbo-0125",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "In the realm of code, recursion dwells,\nA mystical process, where magic swells.\nIt's a dance of functions calling themselves,\nA looping enchantment where logic delves.\n\nLike a mirror reflecting its image anew,\nRecursion mirrors code, recursive through and through.\nA function, encountering its own essence kind,\nUntil a base case breaks the bind.\n\nWith elegance and power, recursion reigns,\nUnraveling problems, breaking chains.\nIt dives deep into the heart of the task,\nUnraveling complexities, an intricate mask.\n\nSo heed the call of recursion's art,\nA looping symphony, playing its part.\nIn the grand symphony of code's design,\nRecursion weaves a pattern divine.",
            },
            "logprobs": None,
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 39, "completion_tokens": 146, "total_tokens": 185},
    "system_fingerprint": "fp_cbdb91ce3f",
}


def test_mytest(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.openai.com/v1/chat/completions",
        json=response,
        status_code=201,
    )
    from openai import OpenAI

    API_KEY = "sk-abcdefgh"

    client = OpenAI(api_key=API_KEY)
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You are a poetic assistant, skilled in explaining complex programming concepts with creative flair.",
            },
            {
                "role": "user",
                "content": "Compose a poem that explains the concept of recursion in programming.",
            },
        ],
    )
    lines = completion.choices[0].message.content.splitlines()[0:2]
    assert (
        "\n".join(lines)
        == "In the realm of code, recursion dwells,\nA mystical process, where magic swells."
    )
