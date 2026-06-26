using Ardalis.Specification;
using CleanArchitectureCosmosDB.Core.Entities;
using CleanArchitectureCosmosDB.Core.Specifications;
using CleanArchitectureCosmosDB.Core.Specifications.Base;
using System.Collections.Generic;
using System.Linq;
using Xunit;

namespace CleanArchitectureCosmosDB.UnitTests.CosmosB
{
    /// <summary>
    ///     The aggregation specification feeds the TotalRecordsMatched count on search.
    ///     If only the record specification learns the completion filter and this one
    ///     does not, the count disagrees with the page — so it gets its own coverage.
    /// </summary>
    public class ToDoItemSearchAggregationSpecificationTest
    {
        private static int Count(ISpecification<ToDoItem> spec, IEnumerable<ToDoItem> items)
        {
            CosmosDbSpecificationEvaluator<ToDoItem> evaluator = new CosmosDbSpecificationEvaluator<ToDoItem>();
            return evaluator.GetQuery(items.AsQueryable(), spec).Count();
        }

        private static List<ToDoItem> SampleItems()
        {
            ToDoItem done = new ToDoItem() { Id = "work:1", Category = "work", Title = "Done item" };
            done.MarkComplete();
            ToDoItem open1 = new ToDoItem() { Id = "work:2", Category = "work", Title = "Open item A" };
            ToDoItem open2 = new ToDoItem() { Id = "home:3", Category = "home", Title = "Open item B" };

            return new List<ToDoItem> { done, open1, open2 };
        }

        [Fact]
        public void IsCompletedTrue_CountsOnlyCompletedItems()
        {
            List<ToDoItem> items = SampleItems();

            ToDoItemSearchAggregationSpecification spec = new ToDoItemSearchAggregationSpecification(isCompleted: true);

            Assert.Equal(1, Count(spec, items));
        }

        [Fact]
        public void IsCompletedFalse_CountsOnlyIncompleteItems()
        {
            List<ToDoItem> items = SampleItems();

            ToDoItemSearchAggregationSpecification spec = new ToDoItemSearchAggregationSpecification(isCompleted: false);

            Assert.Equal(2, Count(spec, items));
        }

        [Fact]
        public void IsCompletedNull_CountsAllItems()
        {
            List<ToDoItem> items = SampleItems();

            ToDoItemSearchAggregationSpecification spec = new ToDoItemSearchAggregationSpecification();

            Assert.Equal(3, Count(spec, items));
        }
    }
}
