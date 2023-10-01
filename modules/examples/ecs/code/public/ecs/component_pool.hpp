#pragma once

#include <array>
#include <cassert>
#include <cstdint>
#include <memory>
#include <vector>

#include "CppReflection/Type.hpp"
#include "EverydayTools/Bitset/BitsetAdapter.hpp"
#include "EverydayTools/Bitset/BitsetUtilities.hpp"
#include "entity_id.hpp"

namespace ecs::internal
{
template <size_t kCapacity, typename Part>
struct EntityHasComponent
{
    static constexpr size_t kPartBitsCount = 8 * sizeof(Part);
    static constexpr size_t kPartsCount = kCapacity / kPartBitsCount;
    using PartBitsType = edt::BitCountToTypeT<kPartsCount>;
    std::array<Part, kPartsCount> parts{};
    PartBitsType parts_bits = 0;

    void Set(const size_t index, const bool value)
    {
        const size_t part_index = index / kPartBitsCount;
        const size_t index_in_part = index % kPartBitsCount;
        auto& part = parts[part_index];
        const edt::BitsetAdapter part_adapter(part);
        assert(part_adapter.Get(index_in_part) != value);
        part_adapter.Set(index_in_part, value);
        if (value || part == 0)
        {
            edt::BitsetAdapter parts_adapter(parts_bits);
            assert(parts_adapter.Get(part_index) != value);
            parts_adapter.Set(part_index, value);
        }
    }

    bool IsEmpty() const
    {
        return parts_bits == 0;
    }

    template <typename Callback>
    bool ForEachBit(Callback&& callback)
    {
        return edt::BitsetAdapter(parts_bits)
            .ForEachBitWithReturn(
                [&](const size_t part_index)
                {
                    const auto& part = parts[part_index];
                    if (part == 0) return true;
                    return edt::BitsetAdapter(part).ForEachBitWithReturn(
                        [&](const size_t bit_index)
                        {
                            const size_t index_on_page = part_index * kPartBitsCount + bit_index;
                            return callback(index_on_page);
                        });
                });
    }

    static_assert((kCapacity % kPartBitsCount) == 0);
};

}  // namespace ecs::internal

namespace ecs
{
class ComponentPool
{
public:
    using CellIndex = uint32_t;
    using ForEachComponentCallbackRaw = bool (*)(void* user_data, const EntityId entity_id);

    struct ComponentMetadata
    {
        ecs::EntityId entity_id;
    };

private:
    struct Page
    {
        static constexpr CellIndex kCapacity = 1024;
        std::unique_ptr<uint8_t[]> data;  // NOLINT
        uint8_t* aligned = nullptr;
        std::array<ComponentMetadata, kCapacity> metadata;
        internal::EntityHasComponent<kCapacity, uint64_t> component_exists;
    };

public:
    explicit ComponentPool(const cppreflection::Type*);

    CellIndex Alloc(const EntityId entity_id);
    void Free(const CellIndex cell_index);
    void* Get(const CellIndex cell_index)
    {
        const auto [page_index, index_on_page] = DecomposeChecked(cell_index);
        return GetCellPtr(page_index, index_on_page);
    }

    inline const cppreflection::Type* GetType() const noexcept
    {
        return type_;
    }

    inline size_t GetUsedCount() const noexcept
    {
        return used_count_;
    }

    void ForEach(void* user_data, ForEachComponentCallbackRaw callback);

    template <typename Callback>
    void ForEach(Callback&& callback)
    {
        ForEach(
            &callback,
            [](void* user_data, const EntityId entity_id)
            {
                auto& callback = (*reinterpret_cast<Callback*>(user_data));  // NOLINT
                return callback(entity_id);
            });
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
    size_t used_count_ = 0;
    CellIndex first_free_ = 0;
};
}  // namespace ecs
