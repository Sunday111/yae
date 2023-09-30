#include "ecs/component_pool.hpp"

#include <bit>
#include <cassert>

#include "EverydayTools/Bitset/BitsetAdapter.hpp"
#include "EverydayTools/Bitset/BitsetArrayAdapter.hpp"

namespace ecs
{
ComponentPool::ComponentPool(const cppreflection::Type* type) : type_(type)
{
    cell_size_ = std::max(type_->GetInstanceSize(), sizeof(EmptyCell));
    cell_alignment_ = std::max(type_->GetAlignment(), alignof(EmptyCell));
}

ComponentPool::CellIndex ComponentPool::Alloc(const EntityId entity_id)
{
    auto [page_index, index_on_page] = Decompose(first_free_);
    if (page_index >= pages_.size())
    {
        assert(page_index == pages_.size());
        AddPage();
    }

    const auto cell_index = first_free_;
    std::tie(page_index, index_on_page) = DecomposeChecked(cell_index);

    auto cell = GetFreeCell(page_index, index_on_page);
    first_free_ = cell->next;  // Remember next free
    type_->GetSpecialMembers().defaultConstructor(cell);

    // metadata
    {
        auto& page = pages_[page_index];
        page.metadata[index_on_page].entity_id = entity_id;
        edt::BitsetAdapter<uint16_t>(page.part_has_value).Set(index_on_page / Page::kBitsetPartBitsCount, true);
        edt::BitsetArrayAdapter<Page::BitsetPart>(std::span(page.has_value)).Set(index_on_page, true);
    }

    return cell_index;
}

void ComponentPool::Free(const CellIndex cell_index)
{
    const auto [page_index, index_on_page] = DecomposeChecked(cell_index);
    auto cell = GetCellPtr(page_index, index_on_page);
    type_->GetSpecialMembers().destructor(cell);
    const auto empty_cell = reinterpret_cast<EmptyCell*>(cell);  // NOLINT
    empty_cell->next = first_free_;
    first_free_ = static_cast<CellIndex>(cell_index);

    // metadata
    {
        auto& page = pages_[page_index];
        page.metadata[index_on_page].entity_id = EntityId{};

        const auto part_index = index_on_page / Page::kBitsetPartBitsCount;
        const auto index_in_part = index_on_page % Page::kBitsetPartBitsCount;

        auto& part = page.has_value[part_index];
        const edt::BitsetAdapter<Page::BitsetPart> part_adapter(part);

        assert(part_adapter.Get(index_in_part));
        part_adapter.Set(index_in_part, false);

        // part became empty, update top level bitset
        if (part == 0)
        {
            assert(page.part_has_value);
            const edt::BitsetAdapter<uint16_t> parts_adapter(page.part_has_value);
            parts_adapter.Set(part_index, false);
        }
    }
}

void ComponentPool::AddPage()
{
    assert(first_free_ == pages_.size() * Page::kCapacity);
    const size_t bytes_count = cell_size_ * (Page::kCapacity + 1);  // +1 for alignment

    const auto page_index = static_cast<CellIndex>(pages_.size());
    auto& page = pages_.emplace_back();
    page.data.reset(new uint8_t[bytes_count]);  // NOLINT

    size_t aligned_address = reinterpret_cast<size_t>(page.data.get());  // NOLINT
    if (const size_t remainder = aligned_address % cell_alignment_; remainder != 0)
    {
        aligned_address += cell_alignment_ - remainder;
    }

    page.aligned = reinterpret_cast<uint8_t*>(aligned_address);  // NOLINT

    auto next_free = first_free_;
    for (CellIndex index_on_page = 0; index_on_page != Page::kCapacity; ++index_on_page)
    {
        GetFreeCell(page_index, index_on_page)->next = ++next_free;
    }
}

void ComponentPool::ForEach(void* user_data, ForEachComponentCallbackRaw callback)
{
    for (size_t page_index = 0; page_index != pages_.size(); ++page_index)
    {
        const auto& page = pages_[page_index];
        if (page.part_has_value == 0) continue;

        edt::BitsetAdapter(page.part_has_value)
            .ForEachBitWithReturn(
                [&](const size_t part_index)
                {
                    const auto& part = page.has_value[part_index];
                    if (part == 0) return true;
                    return edt::BitsetAdapter(part).ForEachBitWithReturn(
                        [&](const size_t bit_index)
                        {
                            const size_t index_on_page = part_index * Page::kBitsetPartBitsCount + bit_index;
                            auto& component_metadata = page.metadata[index_on_page];
                            return callback(user_data, component_metadata.entity_id);
                        });
                });
    }
}

}  // namespace ecs
