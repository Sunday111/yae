#pragma once

#include <cstddef>

#include "EverydayTools/Bitset/BitsetAdapter.hpp"
#include "EverydayTools/Bitset/BitsetUtilities.hpp"

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
