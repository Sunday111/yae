#pragma once

#include <cassert>
#include <cstdint>
#include <memory>
#include <vector>

#include "CppReflection/Type.hpp"

namespace ecs
{
class ComponentPool
{
public:
    using CellIndex = uint32_t;

private:
    struct Page
    {
        static constexpr CellIndex kCapacity = 1024;
        std::unique_ptr<uint8_t[]> data;  // NOLINT
        uint8_t* aligned = nullptr;
    };

public:
    explicit ComponentPool(const cppreflection::Type*);

    CellIndex Alloc();
    void Free(const CellIndex cell_index);
    void* Get(const CellIndex cell_index)
    {
        const auto [page_index, index_on_page] = DecomposeChecked(cell_index);
        return GetCellPtr(page_index, index_on_page);
    }

private:
    struct EmptyCell
    {
        CellIndex next;
    };

private:
    template <bool checked>
    inline std::pair<uint32_t, uint32_t> DecomposeImpl(const CellIndex cell_index) const
    {
        const uint32_t page_index = cell_index / Page::kCapacity;
        if constexpr (checked) assert(page_index < pages_.size());
        const uint32_t index_on_page = cell_index % Page::kCapacity;
        return {page_index, index_on_page};
    }

    inline std::pair<uint32_t, uint32_t> DecomposeChecked(const CellIndex cell_index) const
    {
        return DecomposeImpl<true>(cell_index);
    }

    inline std::pair<uint32_t, uint32_t> Decompose(const CellIndex cell_index) const
    {
        return DecomposeImpl<false>(cell_index);
    }

    void* GetCellPtr(const uint32_t page_index, const uint32_t index_on_page)
    {
        auto& page = pages_[page_index];
        const auto cell = page.aligned + cell_size_ * index_on_page;  // NOLINT
        return cell;
    }

    EmptyCell* GetFreeCell(const uint32_t page_index, const uint32_t index_on_page)
    {
        const auto cell_raw = GetCellPtr(page_index, index_on_page);
        const auto cell = reinterpret_cast<EmptyCell*>(cell_raw);  // NOLINT
        return cell;
    }

    void AddPage();

private:
    const cppreflection::Type* type_ = nullptr;
    size_t cell_size_ = 0;
    size_t cell_alignment_ = 0;
    std::vector<Page> pages_;  // NOLINT
    CellIndex first_free_ = 0;
};
}  // namespace ecs