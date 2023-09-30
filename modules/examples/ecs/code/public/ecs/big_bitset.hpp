#pragma once

#include <algorithm>
#include <array>
#include <deque>
#include <ranges>
#include <vector>

#include "EverydayTools/Bitset/DynamicBitset.hpp"
#include "entity_id.hpp"

namespace ecs
{
class EntityComponentLookup
{
public:
    using Part = uint64_t;
    // Segments stores 8 parts - 512 bits
    struct Segment
    {
        static constexpr size_t kPartsCount = 8;
        static constexpr size_t kBitsInPart = sizeof(Part) * 8;
        static constexpr size_t kTotalBits = kBitsInPart * kPartsCount;

        // stores actual bits
        std::array<Part, kPartsCount> parts{};

        // index of the first parts stored in parts
        EntityId first{};

        // if bit 0 is zero then part 0 is empty
        uint8_t parts_bits{};
    };

public:
    EntityComponentLookup()
    {
        // create sentinels
        segments_.resize(2);
        segments_.front().first = EntityId::FromValue(0);
        segments_.back().first = EntityId::FromValue(EntityId{}.GetValue() - Segment::kTotalBits);
    }

    void Add(const EntityId entity_id)
    {
        // find segment that strictly greater than entity id
        auto greater_segment = std::ranges::upper_bound(segments_, entity_id, std::less{}, &Segment::first);
        auto segment = greater_segment - 1;
        if (entity_id.GetValue() >= segment->first.GetValue() + Segment::kTotalBits)
        {
            // Add new segment before greater
            segment = segments_.emplace(greater_segment);
            segment->first = EntityId::FromValue(Segment::kTotalBits * (entity_id.GetValue() / Segment::kTotalBits));
        }

        // Now segment exists
        const EntityId::Repr bit_index_in_segment = entity_id.GetValue() - segment->first.GetValue();
        const auto part_index_in_segment = bit_index_in_segment / Segment::kBitsInPart;

        // Set bit in part
        {
            const auto bit_index_in_part = bit_index_in_segment % Segment::kBitsInPart;
            const edt::BitsetAdapter<Part> adapter(segment->parts[part_index_in_segment]);
            adapter.Set(bit_index_in_part, true);
        }

        // Set part bits
        {
            const edt::BitsetAdapter<uint8_t> adapter(segment->parts_bits);
            adapter.Set(part_index_in_segment, true);
        }
    }

    void Remove(const EntityId entity_id)
    {
        const auto segment = std::ranges::upper_bound(segments_, entity_id, std::less{}, &Segment::first) - 1;
        assert(entity_id.GetValue() < segment->first.GetValue() + Segment::kTotalBits);

        // Now segment exists
        const EntityId::Repr bit_index_in_segment = entity_id.GetValue() - segment->first.GetValue();
        const EntityId::Repr part_index_in_segment = bit_index_in_segment / Segment::kBitsInPart;
        auto& part = segment->parts[part_index_in_segment];

        // Set bit in part
        {
            const edt::BitsetAdapter<Part> adapter(part);
            const auto bit_index_in_part = bit_index_in_segment % Segment::kBitsInPart;
            assert(adapter.Get(bit_index_in_part));
            adapter.Set(bit_index_in_part, false);
        }

        if (part) return;

        // Set part bits
        {
            const edt::BitsetAdapter<uint8_t> adapter(segment->parts_bits);
            assert(adapter.Get(part_index_in_segment));
            adapter.Set(part_index_in_segment, false);
        }

        // Delete segment if empty or not sentinel
        if (segment->parts_bits == 0 && segment != segments_.begin() && segment != segments_.end())
        {
            segments_.erase(segment);
        }
    }

    bool Has(const EntityId entity_id) const
    {
        const auto segment = std::ranges::upper_bound(segments_, entity_id, std::less{}, &Segment::first) - 1;
        if (entity_id.GetValue() < segment->first.GetValue() + Segment::kTotalBits)
        {
            const EntityId::Repr bit_index_in_segment = entity_id.GetValue() - segment->first.GetValue();
            const auto part_index_in_segment = bit_index_in_segment / Segment::kBitsInPart;
            if (edt::BitsetAdapter<const uint8_t>(segment->parts_bits).Get(part_index_in_segment))
            {
                const auto bit_index_in_part = bit_index_in_segment % Segment::kBitsInPart;
                const edt::BitsetAdapter<const Part> adapter(segment->parts[part_index_in_segment]);
                return adapter.Get(bit_index_in_part);
            }
        }

        return false;
    }

    size_t GetSegmentsCount() const
    {
        return segments_.size();
    }

private:
    std::deque<Segment> segments_;
};
}  // namespace ecs
