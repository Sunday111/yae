#include "ecs/internal/component_pool.hpp"

#include <bit>
#include <cassert>

#include "EverydayTools/Bitset/BitsetAdapter.hpp"
#include "EverydayTools/Bitset/BitsetArrayAdapter.hpp"

namespace ecs::internal
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

    auto& page = pages_[page_index];
    page.metadata[index_on_page].entity_id = entity_id;
    page.component_exists.Set(index_on_page, true);
    used_count_++;

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

    auto& page = pages_[page_index];
    page.metadata[index_on_page].entity_id = EntityId{};
    page.component_exists.Set(index_on_page, false);
    --used_count_;
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
        auto& page = pages_[page_index];
        if (page.component_exists.IsEmpty()) continue;

        const bool should_continue = page.component_exists.ForEachBit(
            [&](const size_t index_on_page)
            {
                auto& component_metadata = page.metadata[index_on_page];
                return callback(user_data, component_metadata.entity_id);
            });

        if (!should_continue) break;
    }
}

}  // namespace ecs::internal
