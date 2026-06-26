using Ardalis.Specification;
using CleanArchitectureCosmosDB.Core.Entities;
using CleanArchitectureCosmosDB.Core.Specifications;
using CleanArchitectureCosmosDB.Core.Specifications.Base;
using System.Collections.Generic;
using System.Linq;
using Xunit;

namespace CleanArchitectureCosmosDB.UnitTests.CosmosB
{
    public class ToDoItemSearchSpecificationTest
    {
        private static List<ToDoItem> Evaluate(ISpecification<ToDoItem> spec, IEnumerable<ToDoItem> items)
        {
            CosmosDbSpecificationEvaluator<ToDoItem> evaluator = new CosmosDbSpecificationEvaluator<ToDoItem>();
            return evaluator.GetQuery(items.AsQueryable(), spec).ToList();
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
        public void IsCompletedTrue_ReturnsOnlyCompletedItems()
        {
            List<ToDoItem> items = SampleItems();

            ToDoItemSearchSpecification spec = new ToDoItemSearchSpecification(isCompleted: true);
            List<ToDoItem> result = Evaluate(spec, items);

            Assert.Single(result);
            Assert.All(result, x => Assert.True(x.IsCompleted));
        }

        [Fact]
        public void IsCompletedFalse_ReturnsOnlyIncompleteItems()
        {
            List<ToDoItem> items = SampleItems();

            ToDoItemSearchSpecification spec = new ToDoItemSearchSpecification(isCompleted: false);
            List<ToDoItem> result = Evaluate(spec, items);

            Assert.Equal(2, result.Count);
            Assert.All(result, x => Assert.False(x.IsCompleted));
        }

        [Fact]
        public void IsCompletedNull_ReturnsAllItems()
        {
            List<ToDoItem> items = SampleItems();

            ToDoItemSearchSpecification spec = new ToDoItemSearchSpecification();
            List<ToDoItem> result = Evaluate(spec, items);

            Assert.Equal(3, result.Count);
        }

        [Fact]
        public void TitleFilterStillAppliesAlongsideCompletionFilter()
        {
            List<ToDoItem> items = SampleItems();

            ToDoItemSearchSpecification spec = new ToDoItemSearchSpecification(title: "open item a", isCompleted: false);
            List<ToDoItem> result = Evaluate(spec, items);

            Assert.Single(result);
            Assert.Equal("work:2", result[0].Id);
        }
    }
}
