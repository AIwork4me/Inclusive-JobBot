// Direct llama.cpp parser probe. No model or inference backend is loaded.
#include "chat.h"

#include <algorithm>
#include <fstream>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>

static common_json parse_batch(const common_chat_templates * templates, const common_json & suite) {
    common_chat_templates_inputs inputs;
    common_chat_msg user;
    user.role = "user";
    user.content = "Synthetic parser qualification case.";
    inputs.messages = {user};
    inputs.tools = common_chat_tools_parse_oaicompat(suite.at("tools"));
    inputs.parallel_tool_calls = true;
    inputs.reasoning_format = COMMON_REASONING_FORMAT_AUTO;
    common_chat_params applied = common_chat_templates_apply(templates, inputs);
    common_chat_parser_params parser(applied);
    parser.generation_prompt = common_chat_input("<|im_start|>assistant\n");
    parser.parser = std::move(applied.parser);

    if (applied.format != COMMON_CHAT_FORMAT_PEG_NATIVE || !parser.parser.has_rule("tool-0")) {
        throw std::runtime_error("Template did not select the expected native tool parser");
    }

    common_json rows = common_json::array();
    for (const auto & fixture : suite.at("fixtures")) {
        common_json row = {{"id", fixture.at("id")}};
        std::string native = fixture.at("native_output").get<std::string>();
        if (native.rfind("<think>\n", 0) != 0) {
            native = "<think>\n\n</think>\n\n" + native;
        }
        try {
            auto message = common_chat_parse(common_chat_input(native), false, parser);
            row["message"] = message.to_json_oaicompat();
        } catch (const std::runtime_error & error) {
            row["parser_rejected"] = true;
            row["error"] = error.what();
        }

        // Each parse receives the same growing bytes a server session would
        // accumulate. Reassemble the real diff function's deltas separately.
        std::mt19937 random(20261124);
        std::size_t offset = 0;
        common_chat_msg previous;
        common_chat_msg accumulated;
        accumulated.role = previous.role = "assistant";
        try {
            while (offset < native.size()) {
                offset = std::min(native.size(), offset + 1 + random() % 31);
                // Keep the random cuts at UTF-8 code point boundaries.
                while (offset < native.size() && (static_cast<unsigned char>(native[offset]) & 0xc0) == 0x80) {
                    ++offset;
                }
                auto current = common_chat_parse(common_chat_input(native.substr(0, offset)),
                                                 offset < native.size(), parser);
                for (const auto & diff : common_chat_msg_diff::compute_diffs(previous, current)) {
                    accumulated.content += diff.content_delta;
                    accumulated.reasoning_content += diff.reasoning_content_delta;
                    if (diff.tool_call_index == std::string::npos) {
                        continue;
                    }
                    if (accumulated.tool_calls.size() <= diff.tool_call_index) {
                        accumulated.tool_calls.resize(diff.tool_call_index + 1);
                    }
                    auto & call = accumulated.tool_calls[diff.tool_call_index];
                    if (!diff.tool_call_delta.name.empty()) {
                        call.name = diff.tool_call_delta.name;
                    }
                    call.arguments += diff.tool_call_delta.arguments;
                }
                previous = std::move(current);
            }
            row["stream_message"] = accumulated.to_json_oaicompat();
        } catch (const std::runtime_error & error) {
            row["stream_rejected"] = true;
            row["stream_error"] = error.what();
        }
        rows.push_back(std::move(row));
    }
    return rows;
}

int main(int argc, char ** argv) {
    if (argc != 3) {
        std::cerr << "usage: ij06-native-probe CHAT_TEMPLATE SUITE_JSON\n";
        return 2;
    }
    try {
        std::ifstream template_file(argv[1], std::ios::binary);
        std::ifstream suite_file(argv[2], std::ios::binary);
        if (!template_file || !suite_file) {
            throw std::runtime_error("Cannot open parser probe inputs");
        }
        std::string source{std::istreambuf_iterator<char>(template_file), std::istreambuf_iterator<char>()};
        std::string suite_source{std::istreambuf_iterator<char>(suite_file), std::istreambuf_iterator<char>()};
        common_json suite = common_json::parse(suite_source);
        auto templates = common_chat_templates_init(nullptr, source);
        std::cout << parse_batch(templates.get(), suite).dump(2) << "\n";
    } catch (const std::exception & error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
