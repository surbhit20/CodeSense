#include <filesystem>
#include <string>
#include <cstring>
#include <stdexcept>

namespace fs = std::filesystem;

static bool is_hidden(const fs::path& p) {
    const std::string name = p.filename().string();
    return !name.empty() && name[0] == '.';
}

extern "C" {

// Recursively scans `path`, writing newline-separated file paths into `output`.
// Returns the number of regular files found.
// Skips hidden entries (dot-prefixed) and silently skips permission errors.
int scan_directory(const char* path, char* output, int max_size) {
    if (!path || !output || max_size <= 0) return -1;

    std::string result;
    result.reserve(max_size / 2);
    int file_count = 0;

    try {
        fs::recursive_directory_iterator it(
            path,
            fs::directory_options::skip_permission_denied
        );
        fs::recursive_directory_iterator end;

        for (; it != end; ++it) {
            // Skip hidden entries and don't recurse into hidden directories
            if (is_hidden(it->path())) {
                if (it->is_directory()) it.disable_recursion_pending();
                continue;
            }

            const std::string entry_path = it->path().string() + "\n";
            if (static_cast<int>(result.size() + entry_path.size()) >= max_size)
                break;

            result += entry_path;

            if (it->is_regular_file()) ++file_count;
        }
    } catch (const std::exception&) {
        // Propagate partial results rather than crashing
    }

    std::strncpy(output, result.c_str(), max_size - 1);
    output[max_size - 1] = '\0';
    return file_count;
}

// Returns the total number of regular (non-hidden) files under `path`.
int count_files(const char* path) {
    if (!path) return -1;
    int count = 0;
    try {
        for (const auto& entry : fs::recursive_directory_iterator(
                 path, fs::directory_options::skip_permission_denied)) {
            if (entry.is_regular_file() && !is_hidden(entry.path()))
                ++count;
        }
    } catch (const std::exception&) {}
    return count;
}

} // extern "C"
